import json
import logging
from datetime import date, timedelta

from config import get_redis
import db
from pricing.formula import calculate_all_prices

log = logging.getLogger(__name__)


def _get_dates_to_process(trade_date: date) -> list[date]:
    """On Monday, return Fri/Sat/Sun. Otherwise return just today."""
    if trade_date.weekday() == 0:
        return [trade_date - timedelta(days=d) for d in (3, 2, 1)]
    return [trade_date]


def run_daily_pricing(conn, season_id: int, trade_date: date | None = None):
    if trade_date is None:
        trade_date = date.today()

    game_dates = _get_dates_to_process(trade_date)
    log.info("Running daily pricing for season %d, trade_date=%s, game_dates=%s",
             season_id, trade_date, game_dates)

    results = calculate_all_prices(conn, season_id, trade_date)

    if not results:
        log.warning("No price results generated")
        return

    for row in results:
        db.insert_price_history(
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

    try:
        r = get_redis()
        payload = json.dumps([
            {"player_season_id": row["player_season_id"], "price": row["price"],
             "change_pct": row["change_pct"], "market_cap": row["market_cap"]}
            for row in results
        ])
        r.publish("prices", payload)
        log.info("Published prices to Redis")
    except Exception:
        log.exception("Failed to publish prices to Redis")
