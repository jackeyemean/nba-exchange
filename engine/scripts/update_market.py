"""
Update Market: Daily price update. Run at market open to update prices from prior games.

Price on date D = price after last night's games (game_date D-1 in NBA API).
Daily % change = (price D − price D−1) / price D−1.

Flow:
  1. sync_teams, sync_incremental_game_stats (through yesterday), sync_standings
  2. Compute prices for today
  3. Write to price_history (prev_price = yesterday, change_pct = (today - yesterday) / yesterday)
  4. Rebalance indexes

Usage:
    python scripts/update_market.py --season 2025-26
    python scripts/update_market.py --season 2025-26 --date 2026-03-08

Schedule: Run daily at 6:00 AM ET.
Run from engine/ directory.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

_engine_dir = Path(__file__).resolve().parent.parent
if str(_engine_dir) not in sys.path:
    sys.path.insert(0, str(_engine_dir))

import click

from config import get_db_connection
from db.seasons import get_season_by_label
from ingestion.nba import sync_teams
from scripts.daily_update import run_update_for_date
from utils.dates import market_date_today

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("update_market")


@click.command()
@click.option("--season", default="2025-26", help="Season label, e.g. 2025-26")
@click.option("--date", "trade_date_str", default=None, help="Override trade_date (YYYY-MM-DD). Default: today in ET.")
def main(season: str, trade_date_str: str | None):
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
        if trade_date_str:
            trade_date = datetime.strptime(trade_date_str, "%Y-%m-%d").date()
            log.info("Trade date: %s (--date override)", trade_date)
        else:
            trade_date = market_date_today()
            log.info("Trade date: %s (ET)", trade_date)

        sync_teams(conn)

        count = run_update_for_date(conn, season_id, season, trade_date)
        if count == 0:
            log.warning("No price results - skipping")
            return

        log.info("Inserted %d price history rows for %s", count, trade_date)
        log.info("=== Daily Market Update Complete ===")
    except Exception:
        log.exception("Daily market update failed")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
