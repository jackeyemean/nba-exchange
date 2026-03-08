"""
NBA API sync: teams, players, game logs, standings, prior season averages.
Uses utils.api.safe_request for rate limiting and retries.
"""

import logging
import time
from datetime import datetime

from constants import FLOAT_SHARES, TIER_DEFAULT
from formulas.raw_perf import calculate_raw_perf
from utils.api import safe_request

log = logging.getLogger(__name__)


def sync_teams(conn):
    """Sync all NBA teams from nba_api into teams table."""
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


def sync_players(conn, season_id: int, season_label: str, get_tier_fn):
    """
    Fetch all players for the season. Uses get_tier_fn(ext_id) -> tier for each player.
    Year 0: manual overrides + rookies by draft. Non-rookie, non-override get penny_stock initially.
    """
    from nba_api.stats.endpoints import (
        CommonAllPlayers,
        CommonPlayerInfo,
        LeagueDashPlayerStats,
    )

    log.info("Fetching current season player stats...")
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
        tier = get_tier_fn(ext_id)
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

    # Add rostered players with 0 games
    log.info("Fetching rostered players (including those with 0 games)...")
    try:
        time.sleep(0.3)
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

            tier = get_tier_fn(ext_id)
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

    # Fetch birthdates for players missing them
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


def sync_players_uniform(conn, season_id: int, season_label: str, uniform_float_shares: int):
    """Fetch all players for the season with uniform float_shares (for tier bootstrap simulation)."""
    from nba_api.stats.endpoints import (
        CommonAllPlayers,
        CommonPlayerInfo,
        LeagueDashPlayerStats,
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
        time.sleep(0.3)
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


def sync_game_logs(conn, season_id: int, season_label: str):
    """Fetch game logs using bulk LeagueGameLog endpoint (far fewer API calls)."""
    from nba_api.stats.endpoints import LeagueGameLog
    from psycopg2.extras import execute_values

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

        raw_perf = calculate_raw_perf(
            pts, fgm, fga, ftm, fta, fg3m, fg3a, oreb, dreb,
            ast, stl, blk, tov,
        )

        rows_to_insert.append((
            ps_id, game_date_str, game_id, minutes,
            pts, ast, reb, stl, blk, tov, fgm, fga, ftm, fta,
            fg3m, fg3a, oreb, dreb,
            round(raw_perf, 4), round(pts / (2.0 * (fga + 0.44 * fta)) if (fga + 0.44 * fta) > 0 else 0.0, 4),
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


def sync_game_logs_for_dates(
    conn, season_id: int, season_label: str, dates: list
) -> int:
    """
    Fetch game logs via LeagueGameLog (same as restart_simulation), filter by dates, upsert.
    Use for incremental sync (update_market). One API call, no delete.
    """
    from nba_api.stats.endpoints import LeagueGameLog
    from psycopg2.extras import execute_values

    if not dates:
        return 0

    date_strs = {d.isoformat() if hasattr(d, "isoformat") else str(d)[:10] for d in dates}

    with conn.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'game_stats' AND column_name = 'wl'"
        )
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

    log.info("Fetching LeagueGameLog for %s (filtering %d dates)...", season_label, len(dates))
    try:
        resp = safe_request(
            LeagueGameLog,
            season=season_label,
            season_type_all_star="Regular Season",
            player_or_team_abbreviation="P",
        )
        df = resp.get_data_frames()[0]
    except Exception:
        log.exception("Failed to fetch LeagueGameLog")
        return 0

    # Filter to requested dates
    df["_gdate"] = df["GAME_DATE"].astype(str).str[:10]
    df = df[df["_gdate"].isin(date_strs)]
    log.info("Filtered to %d rows for dates %s", len(df), sorted(date_strs))

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

        raw_perf = calculate_raw_perf(
            pts, fgm, fga, ftm, fta, fg3m, fg3a, oreb, dreb,
            ast, stl, blk, tov,
        )
        ts_pct = round(pts / (2.0 * (fga + 0.44 * fta)) if (fga + 0.44 * fta) > 0 else 0.0, 4)

        rows_to_insert.append((
            ps_id, game_date_str, game_id, minutes,
            pts, ast, reb, stl, blk, tov, fgm, fga, ftm, fta,
            fg3m, fg3a, oreb, dreb,
            round(raw_perf, 4), ts_pct, wl,
        ))

    if not rows_to_insert:
        log.info("No game stat rows for dates %s", sorted(date_strs))
        return 0

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
                   minutes = EXCLUDED.minutes,
                   pts = EXCLUDED.pts, ast = EXCLUDED.ast, reb = EXCLUDED.reb,
                   stl = EXCLUDED.stl, blk = EXCLUDED.blk, tov = EXCLUDED.tov,
                   fgm = EXCLUDED.fgm, fga = EXCLUDED.fga, ftm = EXCLUDED.ftm, fta = EXCLUDED.fta,
                   fg3m = EXCLUDED.fg3m, fg3a = EXCLUDED.fg3a, oreb = EXCLUDED.oreb, dreb = EXCLUDED.dreb,
                   raw_perf_score = EXCLUDED.raw_perf_score, ts_pct = EXCLUDED.ts_pct,
                   wl = COALESCE(EXCLUDED.wl, game_stats.wl)""",
            rows_to_insert,
            page_size=1000,
        )
    conn.commit()
    log.info("Upserted %d game stat rows for dates %s", len(rows_to_insert), sorted(date_strs))
    return len(rows_to_insert)


def sync_standings(conn, season_id: int, season_label: str):
    """Fetch standings from nba_api and upsert into team_standings."""
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
