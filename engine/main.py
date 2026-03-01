import logging
import sys
from datetime import date, timedelta

import click
import schedule
import time as time_mod

from config import get_db_connection
import db
from ingestion.nba_stats import sync_teams, sync_players, sync_standings, sync_game_stats
from ingestion.salaries import sync_salaries
from pricing.worker import run_daily_pricing
from indexes.calculator import rebalance_indexes, setup_default_indexes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)


@click.group()
def cli():
    pass


@cli.command()
@click.option("--season", required=True, help="Season label, e.g. 2025-26")
@click.option("--date", "game_date", required=True, help="Game date, e.g. 2025-12-01")
def ingest(season: str, game_date: str):
    """Ingest game stats for a specific date."""
    log.info("Ingesting game stats for %s on %s", season, game_date)
    conn = get_db_connection()
    try:
        sync_game_stats(conn, season, game_date)
    finally:
        conn.close()


@cli.command()
@click.option("--season", required=True, help="Season label, e.g. 2025-26")
def price(season: str):
    """Run the pricing worker once for today."""
    conn = get_db_connection()
    try:
        s = db.get_season_by_label(conn, season)
        if not s:
            log.error("Season %s not found", season)
            return
        run_daily_pricing(conn, s["id"])
    finally:
        conn.close()


@cli.command()
@click.option("--season", required=True, help="Season label, e.g. 2025-26")
def rebalance(season: str):
    """Run index rebalance for today."""
    conn = get_db_connection()
    try:
        s = db.get_season_by_label(conn, season)
        if not s:
            log.error("Season %s not found", season)
            return
        rebalance_indexes(conn, s["id"], date.today())
    finally:
        conn.close()


@cli.command("sync-all")
@click.option("--season", required=True, help="Season label, e.g. 2025-26")
def sync_all(season: str):
    """Full sync: teams, players, standings, salaries."""
    conn = get_db_connection()
    try:
        log.info("Starting full sync for %s", season)
        sync_teams(conn, season)
        sync_players(conn, season)
        sync_standings(conn, season)

        parts = season.split("-")
        season_year = int(parts[0])
        sync_salaries(conn, season_year)

        setup_default_indexes(conn, db.get_season_by_label(conn, season)["id"])
        log.info("Full sync complete")
    finally:
        conn.close()


@cli.command("schedule")
@click.option("--season", required=True, help="Season label, e.g. 2025-26")
def run_schedule(season: str):
    """Run on a daily schedule at 8:00 AM ET."""
    log.info("Starting scheduler for season %s (daily at 08:00 ET)", season)

    def daily_job():
        log.info("Scheduled job triggered")
        conn = get_db_connection()
        try:
            s = db.get_season_by_label(conn, season)
            if not s:
                log.error("Season %s not found", season)
                return

            today = date.today()
            if today.weekday() == 0:
                for offset in (3, 2, 1):
                    d = today - timedelta(days=offset)
                    sync_game_stats(conn, season, d.strftime("%Y-%m-%d"))
            else:
                yesterday = today - timedelta(days=1)
                sync_game_stats(conn, season, yesterday.strftime("%Y-%m-%d"))

            sync_standings(conn, season)
            run_daily_pricing(conn, s["id"], today)
            rebalance_indexes(conn, s["id"], today)
            log.info("Scheduled job complete")
        except Exception:
            log.exception("Scheduled job failed")
        finally:
            conn.close()

    schedule.every().day.at("08:00").do(daily_job)

    while True:
        schedule.run_pending()
        time_mod.sleep(30)


if __name__ == "__main__":
    cli()
