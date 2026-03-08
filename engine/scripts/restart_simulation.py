"""
Restart Simulation: Full market reset. Simulate prior 2 seasons with uniform shares,
determine tiers from performance ranking, then simulate current season with tier-based shares.

Usage:
    python scripts/restart_simulation.py
    python scripts/restart_simulation.py --date 2026-03-08

Run from engine/ directory.
"""

import logging
import sys
from datetime import date, datetime
from pathlib import Path

# Ensure engine/ is on path when running from scripts/
_engine_dir = Path(__file__).resolve().parent.parent
if str(_engine_dir) not in sys.path:
    sys.path.insert(0, str(_engine_dir))

import click

from config import get_db_connection
from constants import SEASON_CONFIGS, UNIFORM_FLOAT_SHARES
from db.rankings import get_end_of_season_ranking
from db.seasons import ensure_season_with_dates
from formulas.compute import compute_historical_prices
from ingestion.nba import (
    fetch_prior_season_averages,
    sync_game_logs,
    sync_players,
    sync_standings,
    sync_teams,
    sync_players_uniform,
)
from indexes.calculator import rebalance_indexes, setup_default_indexes
from utils.dates import market_date_today
from tiers.assignment import assign_tiers_from_ranking
from tiers.year0 import (
    apply_tiers_to_current_season,
    build_rookie_tier_map,
    build_year0_tier_fn,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("restart_simulation")


def _backfill_season_with_uniform_shares(
    conn,
    season_id: int,
    season_label: str,
    season_start: date,
    as_of_date: date,
    prior_avgs: dict,
):
    """Backfill a prior season with uniform shares for all players (for tier ranking)."""
    sync_players_uniform(conn, season_id, season_label, UNIFORM_FLOAT_SHARES)
    sync_game_logs(conn, season_id, season_label)
    sync_standings(conn, season_id, season_label)

    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM price_history WHERE player_season_id IN (SELECT id FROM player_seasons WHERE season_id = %s)",
            (season_id,),
        )
    conn.commit()

    compute_historical_prices(
        conn, season_id, prior_avgs, season_start=season_start, as_of_date=as_of_date
    )


@click.command()
@click.option("--debug", is_flag=True, help="Enable debug logging for index rebalance (IPO, Toronto Raptors, user-held indexes)")
@click.option("--date", "as_of_str", default=None, help="Override as_of_date for 2025-26 (YYYY-MM-DD). Default: today in ET.")
def main(debug: bool, as_of_str: str | None):
    """Run full tier bootstrap simulation: 2 prior seasons (uniform shares) -> tier assignment -> current season."""
    if debug:
        import os
        os.environ["DEBUG_INDEXES"] = "1"
    log.info("=== Restart Simulation ===" + (" [DEBUG]" if debug else ""))

    # Ensure we're run from engine/ so migrations path works
    engine_dir = Path(__file__).resolve().parent.parent
    if Path.cwd() != engine_dir:
        import os
        os.chdir(engine_dir)

    conn = get_db_connection()
    try:
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

        sync_teams(conn)

        # --- Phase 1: Simulate 2023-24 with uniform shares ---
        log.info("--- Phase 1: Simulate 2023-24 (uniform shares) ---")
        cfg_2324 = SEASON_CONFIGS["2023-24"]
        season_id_2324 = ensure_season_with_dates(
            conn, "2023-24", cfg_2324["start"], cfg_2324["end"]
        )
        prior_avgs_2324 = fetch_prior_season_averages("2023-24")
        _backfill_season_with_uniform_shares(
            conn, season_id_2324, "2023-24", cfg_2324["start"], cfg_2324["end"], prior_avgs_2324
        )

        # --- Phase 2: Simulate 2024-25 with uniform shares ---
        log.info("--- Phase 2: Simulate 2024-25 (uniform shares) ---")
        cfg_2425 = SEASON_CONFIGS["2024-25"]
        season_id_2425 = ensure_season_with_dates(
            conn, "2024-25", cfg_2425["start"], cfg_2425["end"]
        )
        prior_avgs_2425 = fetch_prior_season_averages("2024-25")
        _backfill_season_with_uniform_shares(
            conn, season_id_2425, "2024-25", cfg_2425["start"], cfg_2425["end"], prior_avgs_2425
        )

        # --- Phase 3: Determine tiers from end-of-2024-25 ranking ---
        log.info("--- Phase 3: Assign tiers from end-of-2024-25 ranking ---")
        ranking = get_end_of_season_ranking(conn, season_id_2425)
        log.info("Ranked %d players from 2024-25", len(ranking))
        tier_map = assign_tiers_from_ranking(ranking)

        tier_counts = {}
        for t in tier_map.values():
            tier_counts[t] = tier_counts.get(t, 0) + 1
        log.info("Tier distribution: %s", tier_counts)

        # --- Phase 4: Backfill 2025-26 with tier-based shares ---
        log.info("--- Phase 4: Simulate 2025-26 (tier-based shares) ---")
        cfg_2526 = SEASON_CONFIGS["2025-26"]
        season_id_2526 = ensure_season_with_dates(
            conn, "2025-26", cfg_2526["start"], cfg_2526["end"]
        )

        get_tier_fn = build_year0_tier_fn("2025-26")
        sync_players(conn, season_id_2526, "2025-26", get_tier_fn)
        sync_game_logs(conn, season_id_2526, "2025-26")
        sync_standings(conn, season_id_2526, "2025-26")

        rookie_tier_map = build_rookie_tier_map("2025-26")
        log.info("Rookie tier map: %d players from draft", len(rookie_tier_map))
        apply_tiers_to_current_season(conn, season_id_2526, tier_map, rookie_tier_map)

        prior_avgs_2526 = fetch_prior_season_averages("2025-26")

        as_of_date = (
            datetime.strptime(as_of_str, "%Y-%m-%d").date()
            if as_of_str
            else market_date_today()
        )

        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM price_history WHERE player_season_id IN (SELECT id FROM player_seasons WHERE season_id = %s)",
                (season_id_2526,),
            )
        conn.commit()

        compute_historical_prices(
            conn,
            season_id_2526,
            prior_avgs_2526,
            season_start=cfg_2526["start"],
            as_of_date=as_of_date,
        )

        with conn.cursor() as cur:
            cur.execute(
                """UPDATE price_history ph
                   SET market_cap = ROUND(ph.price * ps.float_shares, 2)
                   FROM player_seasons ps
                   WHERE ph.player_season_id = ps.id AND ps.season_id = %s""",
                (season_id_2526,),
            )
        conn.commit()

        # --- Phase 5: Initialize indexes ---
        log.info("--- Phase 5: Initialize indexes for 2025-26 ---")
        setup_default_indexes(conn, season_id_2526)
        # Clear index_history for current season so we don't compound on corrupted data.
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM index_history WHERE trade_date >= %s",
                (cfg_2526["start"],),
            )
            # IPO constituents change each season (new rookies); reset to 1000 by clearing
            # all IPO history so prev_level is empty on first 2025-26 date.
            cur.execute(
                """
                DELETE FROM index_history
                WHERE index_id IN (SELECT id FROM indexes WHERE index_type = 'ipo')
                """,
            )
        conn.commit()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT ph.trade_date FROM price_history ph
                JOIN player_seasons ps ON ph.player_season_id = ps.id
                WHERE ps.season_id = %s
                ORDER BY ph.trade_date
                """,
                (season_id_2526,),
            )
            trade_dates = [row[0] for row in cur.fetchall()]
        # Fetch rookie IDs once (same for all dates) instead of calling DraftHistory API 100+ times
        from indexes.calculator import _get_rookie_external_ids
        rookie_ids = _get_rookie_external_ids(conn, season_id_2526)
        # Pre-fetch season_start and indexes once (same for all dates)
        with conn.cursor() as cur:
            cur.execute("SELECT start_date FROM seasons WHERE id = %s", (season_id_2526,))
            row = cur.fetchone()
            if row and row[0]:
                d = row[0]
                season_start_2526 = d.date() if hasattr(d, "date") else d
            else:
                season_start_2526 = None
            cur.execute("SELECT id, name, index_type, team_id FROM indexes")
            indexes_list = cur.fetchall()
        # Batch commits: commit every 10 dates to reduce overhead
        for i, d in enumerate(trade_dates):
            rebalance_indexes(
                conn, season_id_2526, d, debug=debug,
                rookie_external_ids=rookie_ids,
                season_start=season_start_2526,
                indexes=indexes_list,
                commit=(i + 1) % 10 == 0 or i == len(trade_dates) - 1,
            )
        log.info("Initialized indexes for %d trade dates", len(trade_dates))

        log.info("=== Restart Simulation Complete ===")
    except Exception:
        log.exception("Simulation failed")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
