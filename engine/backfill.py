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

from config import get_db_connection
from pricing.formula import calculate_raw_perf, get_age_multiplier, get_win_pct_multiplier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("backfill")

REQUEST_DELAY = 0.7

# Tier structure: Mag 7 = top 7, Blue Chip = top 40, Growth = top 150, Mid Cap = top 250
# small_cap removed - rest are penny_stock
TIER_RANKS = [
    ("magnificent_7", 7),
    ("blue_chip", 40),
    ("growth", 150),
    ("mid_cap", 250),
]
TIER_DEFAULT = "penny_stock"

# Tier premiums: penny->mid 2x, all other jumps 1.25x
# Shares chosen so: mid=2*penny, growth=1.25*mid, blue=1.25*growth, mag7=1.25*blue
FLOAT_SHARES = {
    "magnificent_7": 10_000_000,
    "blue_chip": 8_000_000,   # mag7/1.25
    "growth": 6_400_000,      # blue/1.25
    "mid_cap": 5_120_000,     # growth/1.25
    "penny_stock": 2_560_000, # mid/2
}

INJURY_FREEZE_GAMES = 30
INJURY_MAX_TOTAL = 0.30

PRICE_CEILING = 275.0
PRICE_EXPONENT = 1.5

SEASON_START = date(2025, 10, 22)

_INJURY_CURVE = []
for _i in range(1, INJURY_FREEZE_GAMES + 1):
    frac = _i / INJURY_FREEZE_GAMES
    _INJURY_CURVE.append(INJURY_MAX_TOTAL * (frac ** 2))


def get_team_win_pcts_as_of_date(conn, season_id: int, as_of_date: date) -> dict[int, float]:
    """Compute each team's win% from game_stats (using wl) for games on or before as_of_date."""
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH team_games AS (
                SELECT DISTINCT ON (ps.team_id, gs.external_game_id) ps.team_id, gs.wl
                FROM game_stats gs
                JOIN player_seasons ps ON gs.player_season_id = ps.id
                WHERE ps.season_id = %s AND gs.game_date <= %s AND gs.wl IN ('W', 'L')
            )
            SELECT team_id,
                   COUNT(*) FILTER (WHERE wl = 'W')::float / NULLIF(COUNT(*), 0) as win_pct
            FROM team_games
            GROUP BY team_id
            """,
            (season_id, as_of_date),
        )
        return {row[0]: float(row[1]) for row in cur.fetchall()}


def get_injury_mult(consecutive_missed: int) -> float:
    if consecutive_missed <= 0:
        return 1.0
    idx = min(consecutive_missed, INJURY_FREEZE_GAMES) - 1
    return max(0.70, 1.0 - _INJURY_CURVE[idx])


def assign_tiers_by_perf(player_perfs: list[tuple[str, float]]) -> dict[str, str]:
    """Given [(ext_id, raw_perf), ...] sorted by perf desc, assign tier labels."""
    tier_map = {}
    for rank, (ext_id, _raw) in enumerate(player_perfs):
        tier = TIER_DEFAULT
        for label, cutoff in TIER_RANKS:
            if rank < cutoff:
                tier = label
                break
        tier_map[ext_id] = tier
    return tier_map


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


def _extract_raw_perf_from_row(row) -> float:
    """Helper to pull all 13 stat fields from a DataFrame row and compute raw perf."""
    pts = float(row.get("PTS", 0) or 0)
    fgm = float(row.get("FGM", 0) or 0)
    fga = float(row.get("FGA", 0) or 0)
    ftm = float(row.get("FTM", 0) or 0)
    fta = float(row.get("FTA", 0) or 0)
    fg3m = float(row.get("FG3M", 0) or 0)
    fg3a = float(row.get("FG3A", 0) or 0)
    oreb = float(row.get("OREB", 0) or 0)
    dreb = float(row.get("DREB", 0) or 0)
    ast = float(row.get("AST", 0) or 0)
    stl = float(row.get("STL", 0) or 0)
    blk = float(row.get("BLK", 0) or 0)
    tov = float(row.get("TOV", 0) or 0)
    return calculate_raw_perf(pts, fgm, fga, ftm, fta, fg3m, fg3a, oreb, dreb, ast, stl, blk, tov)


def _rookie_tier_from_pick(overall_pick: int) -> str:
    """Assign rookie tier based on draft position.
    Lottery (1-14) -> growth, first round/early second (15-39) -> mid_cap, else -> penny_stock."""
    if 1 <= overall_pick <= 14:
        return "growth"
    if 15 <= overall_pick <= 39:
        return "mid_cap"
    return "penny_stock"


# One-time Year 0 tier overrides (first season of Hoop Exchange)
YEAR0_TIER_OVERRIDES = {
    "magnificent_7": ["203999", "1628983", "1629029", "1641705", "203507", "1628369", "1630162"],
    "blue_chip": [
        "1630169", "202681", "203076", "1631114",
        "201939", "1627734", "1626157", "1629027", "1627826", "1629639", "1630596", "1641708",
    ],
    "growth": [
        "202695", "1627742", "1631096",
        "1630581", "1630530", "1628374", "1630552", "1630567", "1630559", "202696",
    ],
    "mid_cap": ["1630166", "1641718", "203954", "1627749"],
    "penny_stock": ["1642263", "1629674", "1642918", "1642404", "1631157", "1629645", "1631212", "1630230"],
}


def backfill_players_and_stats(conn, season_id: int, season_label: str):
    """Fetch all players for the season. Year 0: manual overrides + rookies by draft.
    Non-rookie, non-override players get penny_stock initially; tiers finalized after prices."""
    from nba_api.stats.endpoints import (
        LeagueDashPlayerStats, CommonPlayerInfo, CommonAllPlayers,
    )

    draft_year = int(season_label.split("-")[0])

    # Build manual override map (flat ext_id -> tier)
    manual_tier_map = {}
    for tier, pids in YEAR0_TIER_OVERRIDES.items():
        for pid in pids:
            manual_tier_map[pid] = tier

    # --- Step 1: Build rookie draft position map ---
    log.info("Fetching draft history for %d rookies...", draft_year)
    rookie_tier_map = {}
    try:
        from nba_api.stats.endpoints import DraftHistory
        draft_resp = safe_request(DraftHistory, season_year_nullable=draft_year)
        draft_df = draft_resp.get_data_frames()[0]
        for _, r in draft_df.iterrows():
            pid = str(r["PERSON_ID"])
            pick = int(r.get("OVERALL_PICK", 0) or 0)
            rookie_tier_map[pid] = _rookie_tier_from_pick(pick)
        log.info("Loaded draft positions for %d rookies", len(rookie_tier_map))
    except Exception:
        log.warning("Failed to fetch draft history, rookies will default to penny_stock")

    # --- Step 3: Fetch current season players (those who have played) ---
    log.info("Fetching current season player stats...")
    resp = safe_request(
        LeagueDashPlayerStats, season=season_label,
        season_type_all_star="Regular Season", per_mode_detailed="PerGame",
    )
    df = resp.get_data_frames()[0]
    log.info("Found %d players in season stats", len(df))

    team_id_map = {}
    with conn.cursor() as cur:
        cur.execute("SELECT id, external_id FROM teams")
        for row in cur.fetchall():
            team_id_map[row[1]] = row[0]

    def _get_tier(ext_id: str) -> str:
        if ext_id in manual_tier_map:
            return manual_tier_map[ext_id]
        if ext_id in rookie_tier_map:
            return rookie_tier_map[ext_id]
        return TIER_DEFAULT

    player_rows = []
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
        player_rows.append((ext_id, first_name, last_name, team_db_id))

    seen_ext_ids = set()
    player_count = 0
    for ext_id, first_name, last_name, team_db_id in player_rows:
        tier = _get_tier(ext_id)
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
        seen_ext_ids.add(ext_id)
        player_count += 1

    conn.commit()
    log.info("Synced %d players with game stats", player_count)

    # --- Step 4: Add rostered players with 0 games (injured, etc.) ---
    log.info("Fetching rostered players (including those with 0 games)...")
    try:
        time.sleep(1)
        resp2 = safe_request(CommonAllPlayers, is_only_current_season=1, season=season_label)
        roster_df = resp2.get_data_frames()[0]
        rostered_only = roster_df[roster_df["ROSTERSTATUS"] == 1]

        added = 0
        for _, row in rostered_only.iterrows():
            ext_id = str(row["PERSON_ID"])
            if ext_id in seen_ext_ids:
                continue
            name = row.get("DISPLAY_FIRST_LAST", "")
            parts = name.split(" ", 1) if name else ["", ""]
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ""
            team_ext = str(row.get("TEAM_ID", "0"))
            if not first_name:
                continue
            team_db_id = team_id_map.get(team_ext)
            if not team_db_id:
                continue

            tier = _get_tier(ext_id)
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
                    """INSERT INTO player_seasons (player_id, season_id, team_id, tier, float_shares, status)
                       VALUES (%s, %s, %s, %s, %s, 'active')
                       ON CONFLICT (player_id, season_id) DO UPDATE SET
                           tier = EXCLUDED.tier, float_shares = EXCLUDED.float_shares""",
                    (player_db_id, season_id, team_db_id, tier, FLOAT_SHARES[tier]),
                )
            seen_ext_ids.add(ext_id)
            added += 1

        conn.commit()
        log.info("Added %d rostered players with 0 games played", added)
    except Exception:
        log.warning("Failed to fetch rostered players, continuing with game-stats players only")

    log.info("Total players: %d", len(seen_ext_ids))

    # --- Step 5: Fetch birthdates for players missing them ---
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


def backfill_players_and_stats_uniform(
    conn, season_id: int, season_label: str, uniform_float_shares: int
):
    """Fetch all players for the season with uniform float_shares (for tier bootstrap simulation)."""
    from nba_api.stats.endpoints import (
        LeagueDashPlayerStats,
        CommonPlayerInfo,
        CommonAllPlayers,
    )

    log.info("Fetching current season player stats (uniform shares=%d)...", uniform_float_shares)
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

    player_rows = []
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
        player_rows.append((ext_id, first_name, last_name, team_db_id))

    seen_ext_ids = set()
    player_count = 0
    for ext_id, first_name, last_name, team_db_id in player_rows:
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
                (player_db_id, season_id, team_db_id, TIER_DEFAULT, uniform_float_shares),
            )
            cur.fetchone()
        seen_ext_ids.add(ext_id)
        player_count += 1

    conn.commit()
    log.info("Synced %d players with game stats", player_count)

    log.info("Fetching rostered players (including those with 0 games)...")
    try:
        time.sleep(1)
        resp2 = safe_request(CommonAllPlayers, is_only_current_season=1, season=season_label)
        roster_df = resp2.get_data_frames()[0]
        rostered_only = roster_df[roster_df["ROSTERSTATUS"] == 1]

        added = 0
        for _, row in rostered_only.iterrows():
            ext_id = str(row["PERSON_ID"])
            if ext_id in seen_ext_ids:
                continue
            name = row.get("DISPLAY_FIRST_LAST", "")
            parts = name.split(" ", 1) if name else ["", ""]
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ""
            team_ext = str(row.get("TEAM_ID", "0"))
            if not first_name:
                continue
            team_db_id = team_id_map.get(team_ext)
            if not team_db_id:
                continue

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
                    """INSERT INTO player_seasons (player_id, season_id, team_id, tier, float_shares, status)
                       VALUES (%s, %s, %s, %s, %s, 'active')
                       ON CONFLICT (player_id, season_id) DO UPDATE SET
                           tier = EXCLUDED.tier, float_shares = EXCLUDED.float_shares""",
                    (player_db_id, season_id, team_db_id, TIER_DEFAULT, uniform_float_shares),
                )
            seen_ext_ids.add(ext_id)
            added += 1

        conn.commit()
        log.info("Added %d rostered players with 0 games played", added)
    except Exception:
        log.warning("Failed to fetch rostered players, continuing with game-stats players only")

    log.info("Total players: %d", len(seen_ext_ids))

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
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'game_stats' AND column_name = 'wl'
        """)
        if cur.fetchone() is None:
            cur.execute("ALTER TABLE game_stats ADD COLUMN wl CHAR(1)")
            conn.commit()
            log.info("Added wl column to game_stats")

    with conn.cursor() as cur:
        cur.execute(
            """SELECT ps.id, p.external_id FROM player_seasons ps
               JOIN players p ON ps.player_id = p.id
               WHERE ps.season_id = %s""",
            (season_id,),
        )
        ps_map = {row[1]: row[0] for row in cur.fetchall()}

    with conn.cursor() as cur:
        cur.execute(
            """DELETE FROM game_stats WHERE player_season_id IN
               (SELECT id FROM player_seasons WHERE season_id = %s)""",
            (season_id,),
        )
        log.info("Cleared %d old game_stats rows", cur.rowcount)
    conn.commit()

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

        wl = str(row.get("WL", "") or "")[:1].upper() or None
        if wl and wl not in ("W", "L"):
            wl = None

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
        fg3m = int(row.get("FG3M", 0) or 0)
        fg3a = int(row.get("FG3A", 0) or 0)
        oreb = int(row.get("OREB", 0) or 0)
        dreb = int(row.get("DREB", 0) or 0)

        min_val = row.get("MIN", 0)
        try:
            minutes = float(min_val) if min_val else 0.0
        except (ValueError, TypeError):
            minutes = 0.0

        tsa = fga + 0.44 * fta
        ts_pct = pts / (2.0 * tsa) if tsa > 0 else 0.0
        raw_perf = calculate_raw_perf(
            pts, fgm, fga, ftm, fta, fg3m, fg3a, oreb, dreb,
            ast, stl, blk, tov,
        )

        rows_to_insert.append((
            ps_id, game_date_str, game_id, minutes,
            pts, ast, reb, stl, blk, tov, fgm, fga, ftm, fta,
            fg3m, fg3a, oreb, dreb,
            round(raw_perf, 4), round(ts_pct, 4),
            wl,
        ))

    log.info("Prepared %d stat rows for insertion", len(rows_to_insert))

    with conn.cursor() as cur:
        execute_values(
            cur,
            """INSERT INTO game_stats
                   (player_season_id, game_date, external_game_id, minutes,
                    pts, ast, reb, stl, blk, tov, fgm, fga, ftm, fta,
                    fg3m, fg3a, oreb, dreb,
                    raw_perf_score, ts_pct, wl)
               VALUES %s
               ON CONFLICT (player_season_id, external_game_id) DO UPDATE SET
                   raw_perf_score = EXCLUDED.raw_perf_score, ts_pct = EXCLUDED.ts_pct,
                   wl = COALESCE(EXCLUDED.wl, game_stats.wl)""",
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


def fetch_prior_season_averages(season_label: str) -> dict:
    """Fetch prior season per-game averages for all players. Returns {external_id: raw_perf}."""
    from nba_api.stats.endpoints import LeagueDashPlayerStats

    prior_year = int(season_label.split("-")[0]) - 1
    prior_label = f"{prior_year}-{str(prior_year + 1)[-2:]}"
    log.info("Fetching prior season (%s) averages...", prior_label)

    try:
        resp = safe_request(
            LeagueDashPlayerStats,
            season=prior_label,
            season_type_all_star="Regular Season",
            per_mode_detailed="PerGame",
        )
        df = resp.get_data_frames()[0]
    except Exception:
        log.warning("Failed to fetch prior season data, continuing without priors")
        return {}

    priors = {}
    for _, row in df.iterrows():
        ext_id = str(row["PLAYER_ID"])
        priors[ext_id] = _extract_raw_perf_from_row(row)

    log.info("Loaded prior averages for %d players", len(priors))
    return priors


def compute_historical_prices(
    conn,
    season_id: int,
    prior_avgs: dict,
    season_start: date | None = None,
    as_of_date: date | None = None,
):
    """
    Formula v2: raw performance scores (no cross-player normalization),
    prior-season blend, recent-form weighting, gentle availability discount.

    If season_start is None, uses SEASON_START. If as_of_date is None, uses today.
    """
    start = season_start or SEASON_START
    end = as_of_date or date.today()
    log.info("Computing historical prices (v2 formula) from %s to %s...", start, end)

    PRIOR_BLEND_GAMES = 10
    RECENT_WINDOW = 15
    RECENT_WEIGHT = 0.20

    with conn.cursor() as cur:
        cur.execute(
            """SELECT ps.id, ps.player_id, ps.team_id, ps.float_shares, ps.status,
                      p.birthdate, p.external_id
               FROM player_seasons ps JOIN players p ON ps.player_id = p.id
               WHERE ps.season_id = %s AND ps.status NOT IN ('delisting', 'delisted')""",
            (season_id,),
        )
        all_players = cur.fetchall()

    if not all_players:
        log.warning("No players found")
        return

    STAT_KEYS = ("pts", "fgm", "fga", "ftm", "fta", "fg3m", "fg3a",
                  "oreb", "dreb", "ast", "stl", "blk", "tov")

    game_stats_by_player = {}
    with conn.cursor() as cur:
        cur.execute(
            """SELECT player_season_id, game_date,
                      pts, fgm, fga, ftm, fta, fg3m, fg3a,
                      oreb, dreb, ast, stl, blk, tov
               FROM game_stats gs JOIN player_seasons ps ON gs.player_season_id = ps.id
               WHERE ps.season_id = %s ORDER BY game_date""",
            (season_id,),
        )
        for row in cur.fetchall():
            ps_id = row[0]
            if ps_id not in game_stats_by_player:
                game_stats_by_player[ps_id] = []
            game_stats_by_player[ps_id].append({
                "game_date": row[1],
                "pts": float(row[2]), "fgm": float(row[3]), "fga": float(row[4]),
                "ftm": float(row[5]), "fta": float(row[6]),
                "fg3m": float(row[7]), "fg3a": float(row[8]),
                "oreb": float(row[9]), "dreb": float(row[10]),
                "ast": float(row[11]), "stl": float(row[12]),
                "blk": float(row[13]), "tov": float(row[14]),
            })

    current = start
    trade_days = []
    while current <= end:
        if current.weekday() < 5:
            trade_days.append(current)
        current += timedelta(days=1)

    log.info("Computing prices for %d trading days across %d players...", len(trade_days), len(all_players))

    from psycopg2.extras import execute_values

    price_count = 0
    prev_prices = {}

    for td_idx, trade_date in enumerate(trade_days):
        rows_to_insert = []
        team_win_pcts = get_team_win_pcts_as_of_date(conn, season_id, trade_date)
        all_win_pcts = list(team_win_pcts.values()) if team_win_pcts else []

        # First pass: compute blended_raw for all players this day
        day_data = []
        for ps_id, player_id, team_id, float_shares, status, birthdate, ext_id in all_players:
            stats = game_stats_by_player.get(ps_id, [])
            games_before = [s for s in stats if s["game_date"] <= trade_date]
            n_games = len(games_before)

            prior_raw = prior_avgs.get(ext_id, None)

            if n_games == 0 and prior_raw is None:
                continue

            if n_games > 0:
                season_avg = {k: sum(g[k] for g in games_before) / n_games
                              for k in STAT_KEYS}
                season_raw = calculate_raw_perf(*(season_avg[k] for k in STAT_KEYS))
            else:
                season_raw = 0.0

            if n_games > 0:
                recent_games = games_before[-RECENT_WINDOW:]
                recent_n = len(recent_games)
                recent_avg = {k: sum(g[k] for g in recent_games) / recent_n
                              for k in STAT_KEYS}
                recent_raw = calculate_raw_perf(*(recent_avg[k] for k in STAT_KEYS))
                blended_raw = (1 - RECENT_WEIGHT) * season_raw + RECENT_WEIGHT * recent_raw
            else:
                blended_raw = 0.0

            if prior_raw is not None and n_games < PRIOR_BLEND_GAMES:
                prior_weight = 1.0 - (n_games / PRIOR_BLEND_GAMES)
                if n_games == 0:
                    blended_raw = prior_raw
                else:
                    blended_raw = (1 - prior_weight) * blended_raw + prior_weight * prior_raw

            perf_score = max(0.5, blended_raw)
            day_data.append((ps_id, player_id, team_id, float_shares, status, birthdate,
                            ext_id, perf_score, blended_raw, games_before, n_games, prior_raw))

        max_raw = max(d[8] for d in day_data) if day_data else 100.0  # blended_raw
        age_perf_scale = max_raw if max_raw > 0 else 100.0

        for (ps_id, player_id, team_id, float_shares, status, birthdate, ext_id,
             perf_score, blended_raw, games_before, n_games, prior_raw) in day_data:
            normalized = perf_score / 100.0  # No cap — elite performers can exceed $275 base
            base_price = (normalized ** PRICE_EXPONENT) * PRICE_CEILING

            # Normalize perf for age mult so top performer that day gets 1.0 (reaches 1.4x ceiling)
            age_perf_score = min(100.0, blended_raw / age_perf_scale * 100.0)
            age_mult = get_age_multiplier(birthdate, age_perf_score)

            if n_games > 0:
                last_game = max(s["game_date"] for s in games_before)
                days_since = (trade_date - last_game).days
                consecutive_missed = max(0, (days_since - 2) // 2)
            elif prior_raw is not None:
                days_into = (trade_date - start).days
                consecutive_missed = max(0, days_into // 2)
            else:
                consecutive_missed = 0

            injury_mult = get_injury_mult(consecutive_missed)
            win_pct = team_win_pcts.get(team_id, 0.5)
            win_pct_mult = get_win_pct_multiplier(win_pct, all_win_pcts)

            raw_score = base_price * age_mult * injury_mult * win_pct_mult
            price = round(raw_score, 2)
            if price < 0.01:
                price = 0.01
            mcap = round(price * float_shares, 2)

            prev_price = prev_prices.get(ps_id)
            change_pct = None
            if prev_price and prev_price > 0:
                change_pct = round((price - prev_price) / prev_price, 4)

            rows_to_insert.append((
                ps_id, trade_date, round(float(perf_score), 4), float(age_mult),
                round(float(win_pct_mult), 4), round(float(injury_mult), 4), round(float(raw_score), 4), float(price),
                float(mcap), float(prev_price) if prev_price else None,
                float(change_pct) if change_pct is not None else None,
            ))
            prev_prices[ps_id] = price
            price_count += 1

        if rows_to_insert:
            with conn.cursor() as cur:
                execute_values(
                    cur,
                    """INSERT INTO price_history
                           (player_season_id, trade_date, perf_score, age_mult, win_pct_mult,
                            salary_eff_mult, raw_score, price, market_cap, prev_price, change_pct)
                       VALUES %s
                       ON CONFLICT (player_season_id, trade_date) DO UPDATE SET
                           perf_score = EXCLUDED.perf_score, age_mult = EXCLUDED.age_mult,
                           win_pct_mult = EXCLUDED.win_pct_mult, salary_eff_mult = EXCLUDED.salary_eff_mult,
                           raw_score = EXCLUDED.raw_score, price = EXCLUDED.price,
                           market_cap = EXCLUDED.market_cap, prev_price = EXCLUDED.prev_price,
                           change_pct = EXCLUDED.change_pct""",
                    rows_to_insert,
                    page_size=500,
                )

        if (td_idx + 1) % 10 == 0:
            conn.commit()
            log.info("  ...%d / %d trading days computed", td_idx + 1, len(trade_days))

    conn.commit()
    log.info("Inserted %d price history rows", price_count)


def apply_year0_tiers_from_prices(conn, season_id: int, season_label: str):
    """One-time: manual overrides + rookies by draft. Remaining players fill tier slots by price rank.
    Manual overrides reserve their slots; price-ranked players fill the rest."""
    draft_year = int(season_label.split("-")[0])
    manual_ext_ids = set()
    for pids in YEAR0_TIER_OVERRIDES.values():
        manual_ext_ids.update(pids)

    rookie_tier_map = {}
    try:
        from nba_api.stats.endpoints import DraftHistory
        draft_resp = safe_request(DraftHistory, season_year_nullable=draft_year)
        draft_df = draft_resp.get_data_frames()[0]
        for _, r in draft_df.iterrows():
            pid = str(r["PERSON_ID"])
            pick = int(r.get("OVERALL_PICK", 0) or 0)
            rookie_tier_map[pid] = _rookie_tier_from_pick(pick)
    except Exception:
        log.warning("Could not fetch draft for Year 0 tier assignment")

    with conn.cursor() as cur:
        cur.execute(
            """SELECT ps.id, p.external_id, ph.price
               FROM player_seasons ps
               JOIN players p ON ps.player_id = p.id
               JOIN LATERAL (
                   SELECT price FROM price_history
                   WHERE player_season_id = ps.id ORDER BY trade_date DESC LIMIT 1
               ) ph ON true
               WHERE ps.season_id = %s AND ps.status NOT IN ('delisting', 'delisted')""",
            (season_id,),
        )
        rows = cur.fetchall()

    tier_map = {}
    for ext_id in manual_ext_ids:
        for tier, pids in YEAR0_TIER_OVERRIDES.items():
            if ext_id in pids:
                tier_map[ext_id] = tier
                break
    for ext_id, tier in rookie_tier_map.items():
        tier_map[ext_id] = tier

    price_rankable = [
        (ps_id, ext_id, float(price))
        for ps_id, ext_id, price in rows
        if ext_id not in manual_ext_ids and ext_id not in rookie_tier_map
    ]
    price_rankable.sort(key=lambda x: x[2], reverse=True)

    manual_counts = {t: len(pids) for t, pids in YEAR0_TIER_OVERRIDES.items()}
    slots_remaining = {
        "magnificent_7": 7 - manual_counts.get("magnificent_7", 0),
        "blue_chip": 33 - manual_counts.get("blue_chip", 0),  # 40 - 7
        "growth": 110 - manual_counts.get("growth", 0),  # 150 - 40
        "mid_cap": 100 - manual_counts.get("mid_cap", 0),  # 250 - 150
    }
    tier_order = ["magnificent_7", "blue_chip", "growth", "mid_cap"]
    idx = 0
    for tier in tier_order:
        for _ in range(slots_remaining[tier]):
            if idx >= len(price_rankable):
                break
            _, ext_id, _ = price_rankable[idx]
            tier_map[ext_id] = tier
            idx += 1
    for _, ext_id, _ in price_rankable[idx:]:
        tier_map[ext_id] = TIER_DEFAULT

    for ps_id, ext_id, _ in rows:
        tier = tier_map.get(ext_id, TIER_DEFAULT)
        float_shares = FLOAT_SHARES[tier]
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE player_seasons SET tier = %s, float_shares = %s WHERE id = %s",
                (tier, float_shares, ps_id),
            )
    conn.commit()
    log.info("Applied Year 0 tiers: %d manual/rookie preserved, %d price-ranked",
             len(manual_ext_ids) + len(rookie_tier_map), len(price_rankable))

    with conn.cursor() as cur:
        cur.execute(
            """UPDATE price_history ph
               SET market_cap = ROUND(ph.price * ps.float_shares, 2)
               FROM player_seasons ps
               WHERE ph.player_season_id = ps.id AND ps.season_id = %s""",
            (season_id,),
        )
    conn.commit()
    log.info("Updated market_cap for all price_history rows")


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

        prior_avgs = fetch_prior_season_averages(season)

        log.info("Clearing old price history...")
        with conn.cursor() as cur:
            cur.execute("DELETE FROM price_history WHERE player_season_id IN (SELECT id FROM player_seasons WHERE season_id = %s)", (season_id,))
        conn.commit()
        log.info("Cleared old prices")

        compute_historical_prices(conn, season_id, prior_avgs)

        apply_year0_tiers_from_prices(conn, season_id, season)

        log.info("=== Backfill complete! ===")
    except Exception:
        log.exception("Backfill failed")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
