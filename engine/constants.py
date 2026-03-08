"""
All shared constants for the engine. Single source of truth for tier_bootstrap, backfill, and daily_market_update.
"""

from datetime import date

# ---------------------------------------------------------------------------
# Tiers
# ---------------------------------------------------------------------------
TIER_CUTOFFS = [
    ("magnificent_7", 7),
    ("blue_chip", 40),
    ("growth", 150),
    ("mid_cap", 250),
]
TIER_DEFAULT = "penny_stock"

# ---------------------------------------------------------------------------
# Float shares (per tier, fixed for the season)
# ---------------------------------------------------------------------------
FLOAT_SHARES = {
    "magnificent_7": 12_000_000,
    "blue_chip": 8_000_000,
    "growth": 6_000_000,
    "mid_cap": 5_000_000,
    "penny_stock": 3_000_000,
}

# Same shares for all players during prior-season simulation (tier bootstrap)
UNIFORM_FLOAT_SHARES = 5_000_000

# ---------------------------------------------------------------------------
# Price formula
# ---------------------------------------------------------------------------
PRICE_CEILING = 275.0
PRICE_EXPONENT = 2.5

# Blending: season average vs recent form
PRIOR_BLEND_GAMES = 10
RECENT_WINDOW = 15
RECENT_WEIGHT = 0.20

# ---------------------------------------------------------------------------
# Injury multiplier (quadratic ramp over N games, then capped at 0.70×)
# ---------------------------------------------------------------------------
INJURY_FREEZE_GAMES = 35
INJURY_MAX_TOTAL = 0.35


def _build_injury_curve():
    curve = []
    for i in range(1, INJURY_FREEZE_GAMES + 1):
        frac = i / INJURY_FREEZE_GAMES
        curve.append(INJURY_MAX_TOTAL * (frac ** 2))
    return curve


INJURY_CURVE = _build_injury_curve()


def get_injury_mult(consecutive_missed: int) -> float:
    if consecutive_missed <= 0:
        return 1.0
    idx = min(consecutive_missed, INJURY_FREEZE_GAMES) - 1
    return max(0.70, 1.0 - INJURY_CURVE[idx])

# ---------------------------------------------------------------------------
# API / timing
# ---------------------------------------------------------------------------
REQUEST_DELAY = 0.4

# ---------------------------------------------------------------------------
# Season configs (tier bootstrap)
# ---------------------------------------------------------------------------
SEASON_CONFIGS = {
    "2023-24": {"start": date(2023, 10, 24), "end": date(2024, 4, 14)},
    "2024-25": {"start": date(2024, 10, 22), "end": date(2025, 4, 13)},
    "2025-26": {"start": date(2025, 10, 22), "end": date(2026, 6, 30)},
}
SEASON_START_DEFAULT = date(2025, 10, 22)

# ---------------------------------------------------------------------------
# Game stat keys (for raw perf calculation)
# ---------------------------------------------------------------------------
STAT_KEYS = ("pts", "fgm", "fga", "ftm", "fta", "fg3m", "fg3a", "oreb", "dreb", "ast", "stl", "blk", "tov")

# ---------------------------------------------------------------------------
# Age multiplier (formula.py)
# ---------------------------------------------------------------------------
PRIME_START = 30.0
PRIME_END = 32.0
AGING_CAP_AGE = 40.0
YOUTH_PURE_PER_YEAR = 0.005
YOUTH_PERF_PER_YEAR = 0.15
AGING_PURE_PER_YEAR = 0.02
AGING_PERF_PER_YEAR = 0.03
RAW_PERF_CAP_FOR_AGE = 100.0
AGE_MULT_FLOOR = 0.75
AGE_MULT_CEILING = 2.00

# ---------------------------------------------------------------------------
# Win% multiplier (formula.py)
# ---------------------------------------------------------------------------
WIN_PCT_WORST = 0.90
WIN_PCT_BEST = 1.15

# ---------------------------------------------------------------------------
# Injury shock (formula.py - for injured_out status in daily formula)
# ---------------------------------------------------------------------------
INJURY_SHOCK = 0.70
