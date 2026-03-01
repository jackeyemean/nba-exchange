"""
Backfill script: fetches all 2025-26 season data from nba_api,
computes historical prices for every trading day, and populates PostgreSQL.

Usage:
    python backfill.py --season 2025-26
"""

import logging
import sys
import time
from datetime import date, datetime, timedelta

import click
import numpy as np
import psycopg2

from config import get_db_connection, SCALING_FACTOR
from pricing.formula import (
    calculate_raw_perf,
    get_age_multiplier,
    get_win_pct_multiplier,
    get_salary_efficiency_multiplier,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("backfill")

REQUEST_DELAY = 0.7

TIER_THRESHOLDS = {"superstar": 30, "starter": 24, "rotation": 15}
FLOAT_SHARES = {
    "superstar": 20_000_000,
    "starter": 8_000_000,
    "rotation": 3_000_000,
    "bench": 1_000_000,
}

SEASON_START = date(2025, 10, 22)


def safe_request(endpoint_cls, **kwargs):
    time.sleep(REQUEST_DELAY)
    try:
        return endpoint_cls(**kwargs)
    except Exception as e:
        log.warning("API request failed: %s — retrying in 3s", e)
        time.sleep(3)
        return endpoint_cls(**kwargs)


def ensure_season(conn, label: str):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM seasons WHERE label = %s", (label,))
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute(
            "INSERT INTO seasons (label, start_date, end_date, is_active) VALUES (%s, %s, %s, TRUE) RETURNING id",
            (label, SEASON_START, date(2026, 6, 30)),
        )
        conn.commit()
        return cur.fetchone()[0]


def backfill_teams(conn):
    from nba_api.stats.static import teams as nba_teams

    log.info("Syncing teams...")
    all_teams = nba_teams.get_teams()
    with conn.cursor() as cur:
        for t in all_teams:
            cur.execute(
                """INSERT INTO teams (external_id, name, abbreviation, city)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (external_id) DO UPDATE SET
                       name = EXCLUDED.name, abbreviation = EXCLUDED.abbreviation, city = EXCLUDED.city
                   """,
                (str(t["id"]), t["full_name"], t["abbreviation"], t["city"]),
            )
    conn.commit()
    log.info("Synced %d teams", len(all_teams))


def backfill_players_and_stats(conn, season_id: int, season_label: str):
    """Fetch all player game logs for the season using LeagueDashPlayerStats + PlayerGameLog."""
    from nba_api.stats.endpoints import LeagueDashPlayerStats, CommonPlayerInfo

    log.info("Fetching season player stats...")
    resp = safe_request(
        LeagueDashPlayerStats,
        season=season_label,
        season_type_all_star="Regular Season",
        per_mode_detailed="PerGame",
    )
    df = resp.get_data_frames()[0]
    log.info("Found %d players in season stats", len(df))

    team_id_map = {}
    with conn.cursor() as cur:
        cur.execute("SELECT id, external_id FROM teams")
        for row in cur.fetchall():
            team_id_map[row[1]] = row[0]

    player_count = 0
    for _, row in df.iterrows():
        ext_id = str(row["PLAYER_ID"])
        name = row.get("PLAYER_NAME", "")
        parts = name.split(" ", 1) if name else ["", ""]
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ""
        team_ext = str(row.get("TEAM_ID", "0"))

        if not first_name:
            continue

        team_db_id = team_id_map.get(team_ext)
        if not team_db_id:
            continue

        avg_min = float(row.get("MIN", 0) or 0)
        if avg_min >= TIER_THRESHOLDS["superstar"]:
            tier = "superstar"
        elif avg_min >= TIER_THRESHOLDS["starter"]:
            tier = "starter"
        elif avg_min >= TIER_THRESHOLDS["rotation"]:
            tier = "rotation"
        else:
            tier = "bench"

        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO players (external_id, first_name, last_name)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (external_id) DO UPDATE SET
                       first_name = EXCLUDED.first_name, last_name = EXCLUDED.last_name
                   RETURNING id""",
                (ext_id, first_name, last_name),
            )
            player_db_id = cur.fetchone()[0]

            cur.execute(
                """INSERT INTO player_seasons (player_id, season_id, team_id, tier, float_shares)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (player_id, season_id) DO UPDATE SET
                       team_id = EXCLUDED.team_id, tier = EXCLUDED.tier, float_shares = EXCLUDED.float_shares
                   RETURNING id""",
                (player_db_id, season_id, team_db_id, tier, FLOAT_SHARES[tier]),
            )
            cur.fetchone()

        player_count += 1

    conn.commit()
    log.info("Synced %d players", player_count)

    log.info("Fetching player birthdates (this takes a few minutes)...")
    with conn.cursor() as cur:
        cur.execute(
            "SELECT p.id, p.external_id FROM players p JOIN player_seasons ps ON p.id = ps.player_id WHERE ps.season_id = %s AND p.birthdate IS NULL",
            (season_id,),
        )
        missing_bdays = cur.fetchall()

    fetched = 0
    for pid, ext_id in missing_bdays:
        try:
            resp = safe_request(CommonPlayerInfo, player_id=ext_id)
            info_df = resp.get_data_frames()[0]
            if not info_df.empty:
                bday_str = info_df.iloc[0].get("BIRTHDATE", None)
                position = info_df.iloc[0].get("POSITION", None)
                if bday_str:
                    bday = datetime.strptime(str(bday_str)[:10], "%Y-%m-%d").date()
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE players SET birthdate = %s, position = %s WHERE id = %s",
                            (bday, position, pid),
                        )
            fetched += 1
            if fetched % 50 == 0:
                conn.commit()
                log.info("  ...fetched %d / %d birthdates", fetched, len(missing_bdays))
        except Exception:
            log.debug("Failed to fetch info for player %s", ext_id)

    conn.commit()
    log.info("Fetched %d birthdates", fetched)


def backfill_game_logs(conn, season_id: int, season_label: str):
    """Fetch game logs using bulk LeagueGameLog endpoint (far fewer API calls)."""
    from nba_api.stats.endpoints import LeagueGameLog

    with conn.cursor() as cur:
        cur.execute(
            """SELECT ps.id, p.external_id FROM player_seasons ps
               JOIN players p ON ps.player_id = p.id
               WHERE ps.season_id = %s""",
            (season_id,),
        )
        ps_map = {row[1]: row[0] for row in cur.fetchall()}

    log.info("Fetching bulk game logs for %d players...", len(ps_map))

    try:
        resp = safe_request(
            LeagueGameLog,
            season=season_label,
            season_type_all_star="Regular Season",
            player_or_team_abbreviation="P",
        )
        df = resp.get_data_frames()[0]
        log.info("Bulk game log returned %d rows", len(df))
    except Exception:
        log.exception("Failed to fetch bulk game logs")
        return

    from psycopg2.extras import execute_values

    rows_to_insert = []
    for idx in range(len(df)):
        row = df.iloc[idx]
        player_ext = str(row["PLAYER_ID"])
        ps_id = ps_map.get(player_ext)
        if ps_id is None:
            continue

        game_date_str = str(row["GAME_DATE"])[:10]
        game_id = str(row["GAME_ID"])
        if not game_date_str or not game_id:
            continue

        pts = int(row.get("PTS", 0) or 0)
        ast = int(row.get("AST", 0) or 0)
        reb = int(row.get("REB", 0) or 0)
        stl = int(row.get("STL", 0) or 0)
        blk = int(row.get("BLK", 0) or 0)
        tov = int(row.get("TOV", 0) or 0)
        fgm = int(row.get("FGM", 0) or 0)
        fga = int(row.get("FGA", 0) or 0)
        ftm = int(row.get("FTM", 0) or 0)
        fta = int(row.get("FTA", 0) or 0)

        min_val = row.get("MIN", 0)
        try:
            minutes = float(min_val) if min_val else 0.0
        except (ValueError, TypeError):
            minutes = 0.0

        tsa = fga + 0.44 * fta
        ts_pct = pts / (2.0 * tsa) if tsa > 0 else 0.0
        raw_perf = calculate_raw_perf(pts, ast, reb, stl, blk, tov, ts_pct)

        rows_to_insert.append((
            ps_id, game_date_str, game_id, minutes,
            pts, ast, reb, stl, blk, tov, fgm, fga, ftm, fta,
            round(raw_perf, 4), round(ts_pct, 4),
        ))

    log.info("Prepared %d stat rows for insertion", len(rows_to_insert))

    with conn.cursor() as cur:
        execute_values(
            cur,
            """INSERT INTO game_stats
                   (player_season_id, game_date, external_game_id, minutes,
                    pts, ast, reb, stl, blk, tov, fgm, fga, ftm, fta,
                    raw_perf_score, ts_pct)
               VALUES %s
               ON CONFLICT (player_season_id, external_game_id) DO NOTHING""",
            rows_to_insert,
            page_size=1000,
        )
    conn.commit()
    log.info("Loaded %d total game stat rows", len(rows_to_insert))


def backfill_standings(conn, season_id: int, season_label: str):
    from nba_api.stats.endpoints import LeagueStandings

    log.info("Fetching standings...")
    resp = safe_request(LeagueStandings, league_id="00", season=season_label, season_type="Regular Season")
    df = resp.get_data_frames()[0]

    with conn.cursor() as cur:
        for _, row in df.iterrows():
            team_ext = str(row["TeamID"])
            cur.execute("SELECT id FROM teams WHERE external_id = %s", (team_ext,))
            t = cur.fetchone()
            if not t:
                continue
            wins = int(row.get("WINS", 0))
            losses = int(row.get("LOSSES", 0))
            win_pct = float(row.get("WinPCT", 0))
            cur.execute(
                """INSERT INTO team_standings (team_id, season_id, wins, losses, win_pct, updated_at)
                   VALUES (%s, %s, %s, %s, %s, NOW())
                   ON CONFLICT (team_id, season_id) DO UPDATE SET
                       wins = EXCLUDED.wins, losses = EXCLUDED.losses,
                       win_pct = EXCLUDED.win_pct, updated_at = NOW()""",
                (t[0], season_id, wins, losses, win_pct),
            )
    conn.commit()
    log.info("Synced standings for %d teams", len(df))


def compute_historical_prices(conn, season_id: int):
    """For each weekday from season start to today, compute prices based on cumulative stats."""
    log.info("Computing historical prices...")

    with conn.cursor() as cur:
        cur.execute(
            """SELECT ps.id, ps.player_id, ps.team_id, ps.float_shares, ps.status, p.birthdate
               FROM player_seasons ps JOIN players p ON ps.player_id = p.id
               WHERE ps.season_id = %s AND ps.status NOT IN ('delisting', 'delisted')""",
            (season_id,),
        )
        all_players = cur.fetchall()

    if not all_players:
        log.warning("No players found")
        return

    with conn.cursor() as cur:
        cur.execute("SELECT team_id, win_pct FROM team_standings WHERE season_id = %s", (season_id,))
        standings = {row[0]: float(row[1]) for row in cur.fetchall()}

    all_win_pcts = list(standings.values())

    game_stats_by_player = {}
    with conn.cursor() as cur:
        cur.execute(
            """SELECT player_season_id, game_date, pts, ast, reb, stl, blk, tov, ts_pct
               FROM game_stats gs
               JOIN player_seasons ps ON gs.player_season_id = ps.id
               WHERE ps.season_id = %s
               ORDER BY game_date""",
            (season_id,),
        )
        for row in cur.fetchall():
            ps_id = row[0]
            if ps_id not in game_stats_by_player:
                game_stats_by_player[ps_id] = []
            game_stats_by_player[ps_id].append({
                "game_date": row[1],
                "pts": float(row[2]), "ast": float(row[3]), "reb": float(row[4]),
                "stl": float(row[5]), "blk": float(row[6]), "tov": float(row[7]),
                "ts_pct": float(row[8] or 0),
            })

    today = date.today()
    current = SEASON_START
    trade_days = []
    while current <= today:
        if current.weekday() < 5:
            trade_days.append(current)
        current += timedelta(days=1)

    log.info("Computing prices for %d trading days across %d players...", len(trade_days), len(all_players))

    price_count = 0
    for td_idx, trade_date in enumerate(trade_days):
        raw_perfs = []
        player_info = []

        for ps_id, player_id, team_id, float_shares, status, birthdate in all_players:
            stats = game_stats_by_player.get(ps_id, [])
            games_before = [s for s in stats if s["game_date"] <= trade_date]

            if not games_before:
                raw_perfs.append(0.0)
                player_info.append(None)
                continue

            n = len(games_before)
            avg = {k: sum(g[k] for g in games_before) / n for k in ("pts", "ast", "reb", "stl", "blk", "tov", "ts_pct")}
            raw = calculate_raw_perf(avg["pts"], avg["ast"], avg["reb"], avg["stl"], avg["blk"], avg["tov"], avg["ts_pct"])
            raw_perfs.append(raw)
            player_info.append({
                "ps_id": ps_id, "team_id": team_id, "float_shares": float_shares,
                "status": status, "birthdate": birthdate, "raw": raw,
            })

        arr = np.array(raw_perfs, dtype=float)
        min_r, max_r = arr.min(), arr.max()
        range_r = max_r - min_r if max_r != min_r else 1.0
        norm = ((arr - min_r) / range_r) * 100.0

        with conn.cursor() as cur:
            for i, pi in enumerate(player_info):
                if pi is None:
                    continue

                perf_score = float(norm[i])
                age_mult = get_age_multiplier(pi["birthdate"])
                win_pct = standings.get(pi["team_id"], 0.5)
                win_pct_mult = get_win_pct_multiplier(win_pct, all_win_pcts)
                sal_eff_mult = 1.0

                raw_score = perf_score * age_mult * win_pct_mult * sal_eff_mult
                price = round(raw_score * SCALING_FACTOR, 2)
                if price < 0.01:
                    price = 0.01
                mcap = round(price * pi["float_shares"], 2)

                prev_price = None
                change_pct = None
                if td_idx > 0:
                    cur.execute(
                        "SELECT price FROM price_history WHERE player_season_id = %s AND trade_date < %s ORDER BY trade_date DESC LIMIT 1",
                        (pi["ps_id"], trade_date),
                    )
                    prev_row = cur.fetchone()
                    if prev_row:
                        prev_price = float(prev_row[0])
                        if prev_price > 0:
                            change_pct = round((price - prev_price) / prev_price, 4)

                cur.execute(
                    """INSERT INTO price_history
                           (player_season_id, trade_date, perf_score, age_mult, win_pct_mult,
                            salary_eff_mult, raw_score, price, market_cap, prev_price, change_pct)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (player_season_id, trade_date) DO UPDATE SET
                           perf_score = EXCLUDED.perf_score, price = EXCLUDED.price,
                           market_cap = EXCLUDED.market_cap, prev_price = EXCLUDED.prev_price,
                           change_pct = EXCLUDED.change_pct""",
                    (pi["ps_id"], trade_date, round(perf_score, 4), age_mult,
                     win_pct_mult, sal_eff_mult, round(raw_score, 4), price,
                     mcap, prev_price, change_pct),
                )
                price_count += 1

        if (td_idx + 1) % 10 == 0:
            conn.commit()
            log.info("  ...%d / %d trading days computed", td_idx + 1, len(trade_days))

    conn.commit()
    log.info("Inserted %d price history rows", price_count)


@click.command()
@click.option("--season", default="2025-26", help="Season label")
def main(season: str):
    log.info("=== Backfill starting for season %s ===", season)
    conn = get_db_connection()
    try:
        log.info("Checking schema...")
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.seasons')")
            if cur.fetchone()[0] is None:
                log.info("Running schema migration...")
                with open("../migrations/001_initial_schema.up.sql", "r") as f:
                    sql = f.read()
                cur.execute(sql)
                conn.commit()
                log.info("Schema created")
            else:
                log.info("Schema already exists, skipping migration")

        season_id = ensure_season(conn, season)
        log.info("Season ID: %d", season_id)

        backfill_teams(conn)
        backfill_players_and_stats(conn, season_id, season)
        backfill_game_logs(conn, season_id, season)
        backfill_standings(conn, season_id, season)
        compute_historical_prices(conn, season_id)

        log.info("=== Backfill complete! ===")
    except Exception:
        log.exception("Backfill failed")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
