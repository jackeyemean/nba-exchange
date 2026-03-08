"""
Date-specific game stats ingestion. Uses LeagueGameLog (same as restart_simulation)
filtered by date — one API call, works for 2025-26.
"""

import logging
from datetime import date, timedelta

from ingestion.nba import sync_game_logs_for_dates

log = logging.getLogger(__name__)


def sync_incremental_game_stats(conn, season_id: int, season_label: str, through_date: date | None = None) -> int:
    """
    Fetch game stats for dates from last_game_date through through_date.
    Uses LeagueGameLog (same as restart_simulation) filtered by date — one API call.
    """
    through_date = through_date or (date.today() - timedelta(days=1))

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

    start_date = last_date if last_date else season_start
    if start_date > through_date:
        start_date = through_date
        log.info("Filling gap: syncing %s (last_date=%s was ahead of through_date=%s)", start_date, last_date, through_date)

    dates = []
    d = start_date
    while d <= through_date:
        dates.append(d)
        d += timedelta(days=1)

    if not dates:
        log.info("No new game dates to sync (last=%s, through=%s)", last_date, through_date)
        return 0

    log.info("Syncing game stats for %s through %s (%d dates)", start_date, through_date, len(dates))
    total = sync_game_logs_for_dates(conn, season_id, season_label, dates)
    return total
