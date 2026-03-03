import logging
from datetime import date

import numpy as np

log = logging.getLogger(__name__)

PRIME_START = 28.0
PRIME_END = 32.0
AGING_CAP_AGE = 38.0

YOUTH_PURE_PER_YEAR = 0.007
YOUTH_PERF_PER_YEAR = 0.055   # Elite young players (Flagg, Wemby, etc.) reach 1.4x ceiling
AGING_PURE_PER_YEAR = 0.026
AGING_PERF_PER_YEAR = 0.040   # More aggressive: low-perf older players get bigger tax

RAW_PERF_CAP_FOR_AGE = 100.0
AGE_MULT_FLOOR = 0.70
AGE_MULT_CEILING = 1.40  # Young high performers can get up to 1.40x boost

INJURY_SHOCK = 0.50


def calculate_raw_perf(pts: float, fgm: float, fga: float, ftm: float,
                       fta: float, fg3m: float, fg3a: float, oreb: float,
                       dreb: float, ast: float, stl: float, blk: float,
                       tov: float) -> float:
    fgmi = fga - fgm
    ftmi = fta - ftm
    fg3mi = fg3a - fg3m
    return (
        (pts * 1.0)
        + (fgm * 1.0) + (fgmi * -1.0)
        + (ftm * 1.0) + (ftmi * -1.0)
        + (fg3m * 1.0)
        + (oreb * 1.0) + (dreb * 1.0)
        + (ast * 2.0)
        + (stl * 4.0) + (blk * 4.0)
        + (tov * -2)
    )


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
    """Linear 0.90 (worst) to 1.15 (best) by league rank. Capped +15% / −10%."""
    if not all_team_win_pcts:
        return 1.00
    sorted_pcts = sorted(all_team_win_pcts)
    n = len(sorted_pcts)
    rank = sum(1 for pct in sorted_pcts if pct <= team_win_pct)  # 1=worst, n=best
    if n <= 1:
        return 1.00
    # Linear: rank 1 → 0.90, rank n → 1.15 (25-point spread)
    t = (rank - 1) / (n - 1)
    return 0.90 + 0.25 * t


def calculate_all_prices(conn, season_id: int, trade_date: date, scaling_factor: float) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ps.id, ps.player_id, ps.team_id, ps.float_shares, ps.status,
                   p.birthdate,
                   AVG(gs.pts) as avg_pts, AVG(gs.ast) as avg_ast, AVG(gs.reb) as avg_reb,
                   AVG(gs.stl) as avg_stl, AVG(gs.blk) as avg_blk, AVG(gs.tov) as avg_tov,
                   AVG(gs.ts_pct) as avg_ts_pct
            FROM player_seasons ps
            JOIN players p ON ps.player_id = p.id
            LEFT JOIN game_stats gs ON gs.player_season_id = ps.id
            WHERE ps.season_id = %s AND ps.status NOT IN ('delisting', 'delisted')
            GROUP BY ps.id, ps.player_id, ps.team_id, ps.float_shares, ps.status, p.birthdate
            """,
            (season_id,),
        )
        players = cur.fetchall()

    if not players:
        return []

    raw_perfs = []
    player_data = []
    for row in players:
        ps_id, player_id, team_id, float_shares, status, birthdate = row[:6]
        avg_pts = float(row[6] or 0)
        avg_ast = float(row[7] or 0)
        avg_reb = float(row[8] or 0)
        avg_stl = float(row[9] or 0)
        avg_blk = float(row[10] or 0)
        avg_tov = float(row[11] or 0)
        avg_ts_pct = float(row[12] or 0)

        raw = calculate_raw_perf(avg_pts, avg_ast, avg_reb, avg_stl, avg_blk, avg_tov, avg_ts_pct)
        raw_perfs.append(raw)
        player_data.append({
            "ps_id": ps_id, "player_id": player_id, "team_id": team_id,
            "float_shares": float_shares, "status": status, "birthdate": birthdate,
            "raw_perf": raw,
        })

    raw_arr = np.array(raw_perfs, dtype=float)
    min_raw, max_raw = raw_arr.min(), raw_arr.max()
    range_raw = max_raw - min_raw if max_raw != min_raw else 1.0
    norm_scores = ((raw_arr - min_raw) / range_raw) * 100.0

    with conn.cursor() as cur:
        cur.execute(
            "SELECT team_id, win_pct FROM team_standings WHERE season_id = %s",
            (season_id,),
        )
        standings = {row[0]: float(row[1]) for row in cur.fetchall()}

    all_win_pcts = list(standings.values())

    prev_prices = {}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ph.player_season_id, ph.price
            FROM price_history ph
            WHERE ph.trade_date = (
                SELECT MAX(trade_date) FROM price_history WHERE trade_date < %s
            ) AND ph.player_season_id IN (
                SELECT id FROM player_seasons WHERE season_id = %s
            )
            """,
            (trade_date, season_id),
        )
        for row in cur.fetchall():
            prev_prices[row[0]] = float(row[1])

    results = []
    for i, pd_ in enumerate(player_data):
        perf_score = float(norm_scores[i])
        age_mult = get_age_multiplier(pd_["birthdate"], perf_score)
        win_pct = standings.get(pd_["team_id"], 0.5)
        win_pct_mult = get_win_pct_multiplier(win_pct, all_win_pcts)

        raw_score = perf_score * age_mult * win_pct_mult
        price = raw_score * scaling_factor

        prev_price = prev_prices.get(pd_["ps_id"])

        if pd_["status"] == "injured_out" and prev_price is not None:
            price = prev_price * INJURY_SHOCK

        market_cap = price * pd_["float_shares"]
        change_pct = None
        if prev_price and prev_price > 0:
            change_pct = (price - prev_price) / prev_price

        results.append({
            "player_season_id": pd_["ps_id"],
            "trade_date": trade_date,
            "perf_score": round(perf_score, 4),
            "age_mult": age_mult,
            "win_pct_mult": win_pct_mult,
            "salary_eff_mult": 1.0,
            "raw_score": round(raw_score, 4),
            "price": round(price, 2),
            "market_cap": round(market_cap, 2),
            "prev_price": round(prev_price, 2) if prev_price else None,
            "change_pct": round(change_pct, 4) if change_pct is not None else None,
        })

    return results
