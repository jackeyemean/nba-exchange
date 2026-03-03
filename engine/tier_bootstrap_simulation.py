"""
Tier Bootstrap Simulation: Run full simulation for prior 2 seasons with uniform shares,
determine tiers from performance ranking, then simulate current season with tier-based shares.

Tiers (locked per player for the season, updated only at end-of-season):
  - magnificent_7: Top 7 by end-of-prior-season price
  - blue_chip: Ranks 8-40 (33 players)
  - growth: Ranks 41-150 (110 players)
  - mid_cap: Ranks 151-250 (100 players)
  - penny_stock: Rest (no small_cap)

Usage:
    python tier_bootstrap_simulation.py
"""

import logging
import sys
from datetime import date

import click

from config import get_db_connection
from backfill import (
    backfill_teams,
    backfill_players_and_stats,
    backfill_players_and_stats_uniform,
    backfill_game_logs,
    backfill_standings,
    fetch_prior_season_averages,
    compute_historical_prices,
    safe_request,
    FLOAT_SHARES,
    TIER_DEFAULT,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("tier_bootstrap")

# New tier structure: Mag 7 = top 7, Blue Chip = top 40, Growth = top 150, Mid Cap = top 250
TIER_CUTOFFS = [
    ("magnificent_7", 7),
    ("blue_chip", 40),
    ("growth", 150),
    ("mid_cap", 250),
]
# small_cap removed - everything else is penny_stock

UNIFORM_FLOAT_SHARES = 5_000_000  # Same shares for all players during prior-season simulation

SEASON_CONFIGS = {
    "2023-24": {"start": date(2023, 10, 24), "end": date(2024, 4, 14)},
    "2024-25": {"start": date(2024, 10, 22), "end": date(2025, 4, 13)},
    "2025-26": {"start": date(2025, 10, 22), "end": date(2026, 6, 30)},
}


def ensure_season_with_dates(conn, label: str, start_date: date, end_date: date):
    """Ensure season exists with specific dates."""
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM seasons WHERE label = %s", (label,))
        row = cur.fetchone()
        if row:
            cur.execute(
                "UPDATE seasons SET start_date = %s, end_date = %s WHERE id = %s",
                (start_date, end_date, row[0]),
            )
            conn.commit()
            return row[0]
        cur.execute(
            "INSERT INTO seasons (label, start_date, end_date, is_active) VALUES (%s, %s, %s, TRUE) RETURNING id",
            (label, start_date, end_date),
        )
        conn.commit()
        return cur.fetchone()[0]


def backfill_season_with_uniform_shares(
    conn,
    season_id: int,
    season_label: str,
    season_start: date,
    as_of_date: date,
    prior_avgs: dict,
):
    """Backfill a prior season with uniform shares for all players (for tier ranking)."""
    from backfill import (
        backfill_players_and_stats_uniform,
        backfill_game_logs,
        backfill_standings,
    )

    backfill_players_and_stats_uniform(conn, season_id, season_label, UNIFORM_FLOAT_SHARES)
    backfill_game_logs(conn, season_id, season_label)
    backfill_standings(conn, season_id, season_label)

    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM price_history WHERE player_season_id IN (SELECT id FROM player_seasons WHERE season_id = %s)",
            (season_id,),
        )
    conn.commit()

    compute_historical_prices(
        conn, season_id, prior_avgs, season_start=season_start, as_of_date=as_of_date
    )


def get_end_of_season_ranking(conn, season_id: int) -> list[tuple[str, float]]:
    """
    Get player ranking by price at last trading day of season.
    Returns [(external_id, price), ...] sorted by price descending.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.external_id, ph.price
            FROM price_history ph
            JOIN player_seasons ps ON ph.player_season_id = ps.id
            JOIN players p ON ps.player_id = p.id
            WHERE ps.season_id = %s
              AND ph.trade_date = (
                  SELECT MAX(trade_date) FROM price_history
                  WHERE player_season_id IN (SELECT id FROM player_seasons WHERE season_id = %s)
              )
            ORDER BY ph.price DESC
            """,
            (season_id, season_id),
        )
        return [(str(row[0]), float(row[1])) for row in cur.fetchall()]


def assign_tiers_from_ranking(ranking: list[tuple[str, float]]) -> dict[str, str]:
    """Assign tier to each external_id based on rank. Ranks 0-based."""
    tier_map = {}
    for rank, (ext_id, _price) in enumerate(ranking):
        tier = TIER_DEFAULT
        for label, cutoff in TIER_CUTOFFS:
            if rank < cutoff:
                tier = label
                break
        tier_map[ext_id] = tier
    return tier_map


def _rookie_tier_from_pick(overall_pick: int) -> str:
    """Lottery (1-14) -> growth, first round/early second (15-39) -> mid_cap, else -> penny_stock."""
    if 1 <= overall_pick <= 14:
        return "growth"
    if 15 <= overall_pick <= 39:
        return "mid_cap"
    return "penny_stock"


def _build_rookie_tier_map(season_label: str) -> dict[str, str]:
    """Fetch draft history and return {external_id: tier} for rookies."""
    draft_year = int(season_label.split("-")[0])
    try:
        from nba_api.stats.endpoints import DraftHistory
        draft_resp = safe_request(DraftHistory, season_year_nullable=draft_year)
        draft_df = draft_resp.get_data_frames()[0]
        return {
            str(r["PERSON_ID"]): _rookie_tier_from_pick(int(r.get("OVERALL_PICK", 60) or 60))
            for _, r in draft_df.iterrows()
        }
    except Exception:
        log.warning("Failed to fetch draft history, rookies will default to penny_stock")
        return {}


def apply_tiers_to_current_season(
    conn, season_id: int, tier_map: dict[str, str], rookie_tier_map: dict[str, str] | None = None
):
    """Update player_seasons for current season with tier-based float_shares."""
    with conn.cursor() as cur:
        cur.execute(
            """SELECT ps.id, p.external_id FROM player_seasons ps
               JOIN players p ON ps.player_id = p.id
               WHERE ps.season_id = %s""",
            (season_id,),
        )
        rows = cur.fetchall()

    rookie_tier_map = rookie_tier_map or {}
    for ps_id, ext_id in rows:
        tier = tier_map.get(ext_id) or rookie_tier_map.get(ext_id, TIER_DEFAULT)
        float_shares = FLOAT_SHARES[tier]
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE player_seasons SET tier = %s, float_shares = %s WHERE id = %s",
                (tier, float_shares, ps_id),
            )
    conn.commit()
    log.info("Applied tiers to %d players for current season", len(rows))


@click.command()
def main():
    """Run full tier bootstrap simulation: 2 prior seasons (uniform shares) -> tier assignment -> current season."""
    log.info("=== Tier Bootstrap Simulation ===")
    conn = get_db_connection()
    try:
        # Ensure schema
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.seasons')")
            if cur.fetchone()[0] is None:
                log.info("Running schema migration...")
                with open("../migrations/001_initial_schema.up.sql", "r") as f:
                    sql = f.read()
                cur.execute(sql)
                conn.commit()
                log.info("Schema created")

        backfill_teams(conn)

        # --- Phase 1: Simulate 2023-24 with uniform shares ---
        log.info("--- Phase 1: Simulate 2023-24 (uniform shares) ---")
        cfg_2324 = SEASON_CONFIGS["2023-24"]
        season_id_2324 = ensure_season_with_dates(
            conn, "2023-24", cfg_2324["start"], cfg_2324["end"]
        )
        prior_avgs_2324 = fetch_prior_season_averages("2023-24")  # 2022-23
        backfill_season_with_uniform_shares(
            conn,
            season_id_2324,
            "2023-24",
            cfg_2324["start"],
            cfg_2324["end"],
            prior_avgs_2324,
        )

        # --- Phase 2: Simulate 2024-25 with uniform shares ---
        log.info("--- Phase 2: Simulate 2024-25 (uniform shares) ---")
        cfg_2425 = SEASON_CONFIGS["2024-25"]
        season_id_2425 = ensure_season_with_dates(
            conn, "2024-25", cfg_2425["start"], cfg_2425["end"]
        )
        prior_avgs_2425 = fetch_prior_season_averages("2024-25")  # 2023-24
        backfill_season_with_uniform_shares(
            conn,
            season_id_2425,
            "2024-25",
            cfg_2425["start"],
            cfg_2425["end"],
            prior_avgs_2425,
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

        # Use standard backfill for 2025-26 (with tiers from tier_map)
        from backfill import (
            backfill_players_and_stats,
            backfill_game_logs,
            backfill_standings,
        )

        # We need to run backfill_players_and_stats but then override tiers from tier_map
        backfill_players_and_stats(conn, season_id_2526, "2025-26")
        backfill_game_logs(conn, season_id_2526, "2025-26")
        backfill_standings(conn, season_id_2526, "2025-26")

        # Override tiers: veterans from ranking, rookies from draft position
        rookie_tier_map = _build_rookie_tier_map("2025-26")
        log.info("Rookie tier map: %d players from draft", len(rookie_tier_map))
        apply_tiers_to_current_season(conn, season_id_2526, tier_map, rookie_tier_map)

        prior_avgs_2526 = fetch_prior_season_averages("2025-26")  # 2024-25

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
            as_of_date=date.today(),
        )

        # Recompute market_cap with correct float_shares (tier-based)
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE price_history ph
                   SET market_cap = ROUND(ph.price * ps.float_shares, 2)
                   FROM player_seasons ps
                   WHERE ph.player_season_id = ps.id AND ps.season_id = %s""",
                (season_id_2526,),
            )
        conn.commit()

        log.info("=== Tier Bootstrap Simulation Complete ===")
    except Exception:
        log.exception("Simulation failed")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
