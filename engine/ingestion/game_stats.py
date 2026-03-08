"""
Date-specific game stats ingestion. Fetches games for a given date and upserts into game_stats.
Uses ScoreboardV2 + BoxScoreTraditionalV2 for efficiency (only fetches that day's games).
"""

import logging
from datetime import date, timedelta

from nba_api.stats.endpoints import BoxScoreTraditionalV2, ScoreboardV2

from formulas.raw_perf import calculate_raw_perf
from utils.api import safe_request

log = logging.getLogger(__name__)


def _compute_ts_pct(pts: int, fga: int, fta: int) -> float:
    tsa = fga + 0.44 * fta
    if tsa == 0:
        return 0.0
    return pts / (2.0 * tsa)


def sync_game_stats_for_date(conn, season_label: str, game_date: str) -> int:
    """
    Ingest game stats for a specific date. Returns count of rows upserted.
    """
    log.info("Syncing game stats for %s on %s", season_label, game_date)

    with conn.cursor() as cur:
        cur.execute("SELECT id FROM seasons WHERE label = %s", (season_label,))
        row = cur.fetchone()
        if not row:
            log.error("Season %s not found", season_label)
            return 0
        season_id = row[0]

    try:
        resp = safe_request(ScoreboardV2, game_date=game_date, league_id="00")
        games_df = resp.get_data_frames()[0]
    except Exception as e:
        log.exception("Failed to fetch scoreboard for %s: %s", game_date, e)
        return 0

    if games_df.empty:
        log.info("No games found for %s", game_date)
        return 0

    game_ids = games_df["GAME_ID"].unique().tolist()
    count = 0

    for game_id in game_ids:
        try:
            box = safe_request(BoxScoreTraditionalV2, game_id=game_id)
            player_stats = box.get_data_frames()[0]
        except Exception:
            log.exception("Failed to fetch box score for game %s", game_id)
            continue

        for _, row in player_stats.iterrows():
            player_ext_id = str(row["PLAYER_ID"])

            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT ps.id FROM player_seasons ps
                    JOIN players p ON ps.player_id = p.id
                    WHERE p.external_id = %s AND ps.season_id = %s
                    """,
                    (player_ext_id, season_id),
                )
                ps_row = cur.fetchone()

            if not ps_row:
                continue

            minutes_str = row.get("MIN", "0") or "0"
            try:
                if ":" in str(minutes_str):
                    parts = str(minutes_str).split(":")
                    minutes = float(parts[0]) + float(parts[1]) / 60.0
                else:
                    minutes = float(minutes_str)
            except (ValueError, TypeError):
                minutes = 0.0

            pts = int(row.get("PTS", 0) or 0)
            ast = int(row.get("AST", 0) or 0)
            reb = int(row.get("REB", 0) or 0)
            stl = int(row.get("STL", 0) or 0)
            blk = int(row.get("BLK", 0) or 0)
            tov = int(row.get("TO", 0) or 0)
            fgm = int(row.get("FGM", 0) or 0)
            fga = int(row.get("FGA", 0) or 0)
            ftm = int(row.get("FTM", 0) or 0)
            fta = int(row.get("FTA", 0) or 0)
            fg3m = int(row.get("FG3M", 0) or 0)
            fg3a = int(row.get("FG3A", 0) or 0)
            oreb = int(row.get("OREB", 0) or 0)
            dreb = int(row.get("DREB", 0) or 0)

            ts_pct = _compute_ts_pct(pts, fga, fta)
            raw_perf = calculate_raw_perf(
                pts, fgm, fga, ftm, fta, fg3m, fg3a,
                oreb, dreb, ast, stl, blk, tov,
            )

            wl = str(row.get("WL", "") or "")[:1].upper() or None
            if wl and wl not in ("W", "L"):
                wl = None

            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'game_stats' AND column_name = 'wl'
                    """
                )
                has_wl = cur.fetchone() is not None

            if has_wl:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO game_stats
                            (player_season_id, game_date, external_game_id, minutes,
                             pts, ast, reb, stl, blk, tov, fgm, fga, ftm, fta,
                             fg3m, fg3a, oreb, dreb, raw_perf_score, ts_pct, wl)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (player_season_id, external_game_id) DO UPDATE SET
                            minutes = EXCLUDED.minutes,
                            pts = EXCLUDED.pts, ast = EXCLUDED.ast, reb = EXCLUDED.reb,
                            stl = EXCLUDED.stl, blk = EXCLUDED.blk, tov = EXCLUDED.tov,
                            fgm = EXCLUDED.fgm, fga = EXCLUDED.fga, ftm = EXCLUDED.ftm, fta = EXCLUDED.fta,
                            fg3m = EXCLUDED.fg3m, fg3a = EXCLUDED.fg3a, oreb = EXCLUDED.oreb, dreb = EXCLUDED.dreb,
                            raw_perf_score = EXCLUDED.raw_perf_score, ts_pct = EXCLUDED.ts_pct,
                            wl = COALESCE(EXCLUDED.wl, game_stats.wl)
                        """,
                        (
                            ps_row[0], game_date, str(game_id), minutes,
                            pts, ast, reb, stl, blk, tov, fgm, fga, ftm, fta,
                            fg3m, fg3a, oreb, dreb,
                            round(raw_perf, 4), round(ts_pct, 4), wl,
                        ),
                    )
            else:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO game_stats
                            (player_season_id, game_date, external_game_id, minutes,
                             pts, ast, reb, stl, blk, tov, fgm, fga, ftm, fta,
                             fg3m, fg3a, oreb, dreb, raw_perf_score, ts_pct)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (player_season_id, external_game_id) DO UPDATE SET
                            minutes = EXCLUDED.minutes,
                            pts = EXCLUDED.pts, ast = EXCLUDED.ast, reb = EXCLUDED.reb,
                            stl = EXCLUDED.stl, blk = EXCLUDED.blk, tov = EXCLUDED.tov,
                            fgm = EXCLUDED.fgm, fga = EXCLUDED.fga, ftm = EXCLUDED.ftm, fta = EXCLUDED.fta,
                            fg3m = EXCLUDED.fg3m, fg3a = EXCLUDED.fg3a, oreb = EXCLUDED.oreb, dreb = EXCLUDED.dreb,
                            raw_perf_score = EXCLUDED.raw_perf_score, ts_pct = EXCLUDED.ts_pct
                        """,
                        (
                            ps_row[0], game_date, str(game_id), minutes,
                            pts, ast, reb, stl, blk, tov, fgm, fga, ftm, fta,
                            fg3m, fg3a, oreb, dreb,
                            round(raw_perf, 4), round(ts_pct, 4),
                        ),
                    )
            count += 1

    conn.commit()
    log.info("Synced %d game stat rows for %s", count, game_date)
    return count


def sync_incremental_game_stats(conn, season_id: int, season_label: str, through_date: date | None = None) -> int:
    """
    Fetch only new game stats since the last date in DB. Uses date-by-date API calls
    (ScoreboardV2 + BoxScoreTraditionalV2) instead of bulk LeagueGameLog — much smaller
    payloads, avoids timeouts. Fetches from last_game_date through through_date (default:
    yesterday). Re-fetches last_date to catch late games (e.g. March 6 games that finish
    after midnight and appear under March 7 in the API).
    """
    through_date = through_date or (date.today() - timedelta(days=1))

    # Ensure wl column exists (for team win% in price formula)
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
            """
            SELECT MAX(gs.game_date)::date
            FROM game_stats gs
            JOIN player_seasons ps ON gs.player_season_id = ps.id
            WHERE ps.season_id = %s
            """,
            (season_id,),
        )
        row = cur.fetchone()
        last_date = row[0] if row and row[0] else None

    with conn.cursor() as cur:
        cur.execute("SELECT start_date FROM seasons WHERE id = %s", (season_id,))
        row = cur.fetchone()
        season_start = row[0].date() if row and row[0] and hasattr(row[0], "date") else date(2025, 10, 22)

    # Include last_date to re-fetch and catch late games (e.g. March 6 games finishing after midnight)
    start_date = last_date if last_date else season_start
    if start_date > through_date:
        log.info("No new game dates to sync (last=%s, through=%s)", last_date, through_date)
        return 0

    log.info("Syncing incremental game stats from %s through %s", start_date, through_date)
    total = 0
    d = start_date
    while d <= through_date:
        count = sync_game_stats_for_date(conn, season_label, d.isoformat())
        total += count
        d += timedelta(days=1)

    log.info("Synced %d total game stat rows across %d dates", total, (through_date - start_date).days + 1)
    return total
