"""Multipliers: age, win%, injury. All constants from constants.py."""

from datetime import date

from constants import (
    AGE_MULT_CEILING,
    AGE_MULT_FLOOR,
    AGING_CAP_AGE,
    AGING_PERF_PER_YEAR,
    AGING_PURE_PER_YEAR,
    PRIME_END,
    PRIME_START,
    RAW_PERF_CAP_FOR_AGE,
    WIN_PCT_BEST,
    WIN_PCT_WORST,
    YOUTH_PERF_PER_YEAR,
    YOUTH_PURE_PER_YEAR,
    get_injury_mult,
)

__all__ = ["get_age_multiplier", "get_win_pct_multiplier", "get_injury_mult"]


def get_age_multiplier(birthdate: date | None, perf_score: float = 50.0) -> float:
    """Two-component year-by-year age multiplier.

    Component 1 (pure): fixed boost/tax per year away from prime, always applies.
    Component 2 (perf-scaled): additional boost/tax scaled by performance.
    Prime window (28-32): both components are zero.
    Aging penalty caps at age 38 (38+ treated identically).
    """
    if birthdate is None:
        return 1.00
    age = (date.today() - birthdate).days / 365.25
    norm = min(1.0, max(0.0, perf_score / RAW_PERF_CAP_FOR_AGE))

    if age < PRIME_START:
        years_below = PRIME_START - age
        pure = YOUTH_PURE_PER_YEAR * years_below
        perf_comp = YOUTH_PERF_PER_YEAR * years_below * norm
        return min(AGE_MULT_CEILING, 1.0 + pure + perf_comp)
    elif age >= PRIME_END:
        years_above = min(age, AGING_CAP_AGE) - PRIME_END
        pure = AGING_PURE_PER_YEAR * years_above
        perf_comp = AGING_PERF_PER_YEAR * years_above * (1.0 - norm)
        return max(AGE_MULT_FLOOR, 1.0 - pure - perf_comp)
    return 1.00


def get_win_pct_multiplier(team_win_pct: float, all_team_win_pcts: list[float]) -> float:
    """Linear 0.90 (worst) to 1.15 (best) by league rank."""
    if not all_team_win_pcts:
        return 1.00
    sorted_pcts = sorted(all_team_win_pcts)
    n = len(sorted_pcts)
    rank = sum(1 for pct in sorted_pcts if pct <= team_win_pct)  # 1=worst, n=best
    if n <= 1:
        return 1.00
    t = (rank - 1) / (n - 1)
    return WIN_PCT_WORST + (WIN_PCT_BEST - WIN_PCT_WORST) * t
