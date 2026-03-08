"""
Update Market: Daily price update. Run at market open to update prices from prior games.

Uses incremental game sync (date-by-date) instead of bulk LeagueGameLog to avoid timeouts:
  1. sync_teams, sync_incremental_game_stats (only new dates since last in DB), sync_standings
  2. Compute prices for today (compute_prices_for_single_date - same formula as compute_historical_prices)
  3. Write to price_history
  4. Rebalance indexes

Usage:
    python scripts/update_market.py --season 2025-26

Schedule: Run daily at 6:00 AM ET (e.g. via GitHub Actions, cron, or systemd timer).
Run from engine/ directory.
"""

import logging
import sys
from datetime import date
from pathlib import Path

_engine_dir = Path(__file__).resolve().parent.parent
if str(_engine_dir) not in sys.path:
    sys.path.insert(0, str(_engine_dir))

import click

from config import get_db_connection
from db.prices import get_prev_prices, insert_price_history
from db.seasons import get_season_by_label
from formulas.compute import compute_prices_for_single_date
from ingestion.game_stats import sync_incremental_game_stats
from ingestion.nba import (
    fetch_prior_season_averages,
    sync_standings,
    sync_teams,
)
from indexes.calculator import rebalance_indexes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("update_market")


@click.command()
@click.option("--season", default="2025-26", help="Season label, e.g. 2025-26")
def main(season: str):
    log.info("=== Daily Market Update for %s ===", season)

    engine_dir = Path(__file__).resolve().parent.parent
    if Path.cwd() != engine_dir:
        import os
        os.chdir(engine_dir)

    conn = get_db_connection()
    try:
        s = get_season_by_label(conn, season)
        if not s:
            log.error("Season %s not found", season)
            sys.exit(1)

        season_id = s["id"]
        trade_date = date.today()

        sync_teams(conn)

        log.info("Syncing incremental game stats (new dates only)...")
        try:
            sync_incremental_game_stats(conn, season_id, season)
        except Exception as e:
            log.warning("Game stats sync failed (NBA API may be unreachable from this network): %s — continuing with existing data", e)

        log.info("Syncing standings...")
        try:
            sync_standings(conn, season_id, season)
        except Exception as e:
            log.warning("Standings sync failed: %s — continuing (win%% uses game_stats, not standings)", e)

        prior_avgs = fetch_prior_season_averages(season)
        season_start = s["start_date"]
        if hasattr(season_start, "date"):
            season_start = season_start.date()
        prev_prices = get_prev_prices(conn, season_id, trade_date)

        results = compute_prices_for_single_date(
            conn, season_id, prior_avgs, season_start, trade_date, prev_prices
        )

        if not results:
            log.warning("No price results - skipping insert and rebalance")
            return

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
        conn.commit()
        log.info("Inserted %d price history rows for %s", len(results), trade_date)

        rebalance_indexes(conn, season_id, trade_date)
        conn.commit()

        log.info("=== Daily Market Update Complete ===")
    except Exception:
        log.exception("Daily market update failed")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
