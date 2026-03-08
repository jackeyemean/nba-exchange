"""
Shared daily update logic. Used by update_market (single day) and restart_simulation (each day of 2025-26).
Ensures both paths use identical price computation and index rebalancing.
"""

import logging
from datetime import date, timedelta

from db.prices import get_prev_prices, insert_price_history
from formulas.compute import compute_prices_for_single_date
from ingestion.game_stats import sync_incremental_game_stats
from ingestion.nba import fetch_prior_season_averages, sync_standings
from indexes.calculator import rebalance_indexes

log = logging.getLogger(__name__)


def run_update_for_date(
    conn,
    season_id: int,
    season_label: str,
    trade_date: date,
    *,
    skip_game_sync: bool = False,
    prior_avgs: dict | None = None,
    season_start: date | None = None,
    rookie_external_ids: set | None = None,
    indexes: list | None = None,
    commit: bool = True,
    debug: bool = False,
) -> int:
    """
    Run one day's market update: sync game stats (optional), standings, compute prices, insert, rebalance indexes.
    Returns number of price rows inserted.
    """
    if prior_avgs is None:
        prior_avgs = fetch_prior_season_averages(season_label)
    if season_start is None:
        with conn.cursor() as cur:
            cur.execute("SELECT start_date FROM seasons WHERE id = %s", (season_id,))
            row = cur.fetchone()
            if row and row[0]:
                d = row[0]
                season_start = d.date() if hasattr(d, "date") else d
            else:
                season_start = date(2025, 10, 22)

    if not skip_game_sync:
        try:
            sync_incremental_game_stats(
                conn, season_id, season_label, through_date=trade_date - timedelta(days=1)
            )
        except Exception as e:
            log.warning("Game stats sync failed: %s — continuing with existing data", e)

    try:
        sync_standings(conn, season_id, season_label)
    except Exception as e:
        log.warning("Standings sync failed: %s — continuing", e)

    prev_prices = get_prev_prices(conn, season_id, trade_date)
    results = compute_prices_for_single_date(
        conn, season_id, prior_avgs, season_start, trade_date, prev_prices
    )

    if not results:
        return 0

    for row in results:
        insert_price_history(
            conn,
            player_season_id=row["player_season_id"],
            trade_date=row["trade_date"],
            perf_score=row["perf_score"],
            age_mult=row["age_mult"],
            win_pct_mult=row["win_pct_mult"],
            salary_eff_mult=row["salary_eff_mult"],
            raw_score=row["raw_score"],
            price=row["price"],
            market_cap=row["market_cap"],
            prev_price=row["prev_price"],
            change_pct=row["change_pct"],
        )

    if commit:
        conn.commit()

    rebalance_indexes(
        conn,
        season_id,
        trade_date,
        debug=debug,
        rookie_external_ids=rookie_external_ids,
        season_start=season_start,
        indexes=indexes,
        commit=commit,
    )

    return len(results)
