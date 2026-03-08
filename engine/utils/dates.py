"""Date helpers: trading days, game dates to ingest."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


def market_date_today() -> date:
    """Return today's date in ET. Use for trade_date so market logic is timezone-consistent."""
    return datetime.now(ET).date()


def trading_days_in_range(start: date, end: date) -> list[date]:
    """Return list of all calendar days from start through end inclusive.
    Market is open every day: weekdays 6am-6pm ET, weekends 6am-1pm ET."""
    result = []
    current = start
    while current <= end:
        result.append(current)
        current += timedelta(days=1)
    return result


def game_dates_to_ingest(trade_date: date) -> list[date]:
    """On Monday, ingest Fri/Sat/Sun. Otherwise ingest yesterday."""
    if trade_date.weekday() == 0:  # Monday
        return [trade_date - timedelta(days=d) for d in (3, 2, 1)]
    return [trade_date - timedelta(days=1)]
