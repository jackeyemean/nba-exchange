"""
Price computation: historical batch and single-date.
Uses formulas.raw_perf, formulas.multipliers.
"""

import logging
from datetime import date, timedelta

from psycopg2.extras import execute_values

from constants import (
    PRICE_CEILING,
    PRIOR_BLEND_GAMES,
    PRICE_EXPONENT,
    RECENT_WINDOW,
    RECENT_WEIGHT,
    SEASON_START_DEFAULT,
    STAT_KEYS,
    get_injury_mult,
)
from formulas.multipliers import get_age_multiplier, get_win_pct_multiplier
from formulas.raw_perf import calculate_raw_perf
from utils.dates import trading_days_in_range

log = logging.getLogger(__name__)


def get_team_win_pcts_as_of_date(conn, season_id: int, as_of_date: date) -> dict[int, float]:
    """Compute each team's win% from game_stats (using wl) for games on or before as_of_date."""
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH team_games AS (
                SELECT DISTINCT ON (ps.team_id, gs.external_game_id) ps.team_id, gs.wl
                FROM game_stats gs
                JOIN player_seasons ps ON gs.player_season_id = ps.id
                WHERE ps.season_id = %s AND gs.game_date <= %s AND gs.wl IN ('W', 'L')
                ORDER BY ps.team_id, gs.external_game_id, gs.wl DESC
            )
            SELECT team_id,
                   COUNT(*) FILTER (WHERE wl = 'W')::float / NULLIF(COUNT(*), 0) as win_pct
            FROM team_games
            GROUP BY team_id
            """,
            (season_id, as_of_date),
        )
        return {row[0]: float(row[1]) for row in cur.fetchall()}


def compute_historical_prices(
    conn,
    season_id: int,
    prior_avgs: dict,
    season_start: date | None = None,
    as_of_date: date | None = None,
):
    """
    Formula v2: raw performance scores (no cross-player normalization),
    prior-season blend, recent-form weighting, gentle availability discount.

    If season_start is None, uses SEASON_START_DEFAULT. If as_of_date is None, uses today.
    """
    start = season_start or SEASON_START_DEFAULT
    end = as_of_date or date.today()
    log.info("Computing historical prices (v2 formula) from %s to %s...", start, end)

    with conn.cursor() as cur:
        cur.execute(
            """SELECT ps.id, ps.player_id, ps.team_id, ps.float_shares, ps.status,
                      p.birthdate, p.external_id
               FROM player_seasons ps JOIN players p ON ps.player_id = p.id
               WHERE ps.season_id = %s AND ps.status NOT IN ('delisting', 'delisted')""",
            (season_id,),
        )
        all_players = cur.fetchall()

    if not all_players:
        log.warning("No players found")
        return

    game_stats_by_player = {}
    with conn.cursor() as cur:
        cur.execute(
            """SELECT player_season_id, game_date,
                      pts, fgm, fga, ftm, fta, fg3m, fg3a,
                      oreb, dreb, ast, stl, blk, tov
               FROM game_stats gs JOIN player_seasons ps ON gs.player_season_id = ps.id
               WHERE ps.season_id = %s ORDER BY game_date""",
            (season_id,),
        )
        for row in cur.fetchall():
            ps_id = row[0]
            if ps_id not in game_stats_by_player:
                game_stats_by_player[ps_id] = []
            game_stats_by_player[ps_id].append({
                "game_date": row[1],
                "pts": float(row[2]), "fgm": float(row[3]), "fga": float(row[4]),
                "ftm": float(row[5]), "fta": float(row[6]),
                "fg3m": float(row[7]), "fg3a": float(row[8]),
                "oreb": float(row[9]), "dreb": float(row[10]),
                "ast": float(row[11]), "stl": float(row[12]),
                "blk": float(row[13]), "tov": float(row[14]),
            })

    trade_days = trading_days_in_range(start, end)
    log.info("Computing prices for %d trading days across %d players...", len(trade_days), len(all_players))

    price_count = 0
    prev_prices = {}

    for td_idx, trade_date in enumerate(trade_days):
        rows_to_insert = []
        # Use games *before* trade_date so each day's price = "as of market open" (previous day's close).
        # This makes daily change = impact of previous day's games (works for both restart and update_market).
        games_cutoff = trade_date - timedelta(days=1) if trade_date else trade_date
        team_win_pcts = get_team_win_pcts_as_of_date(conn, season_id, games_cutoff)
        all_win_pcts = list(team_win_pcts.values()) if team_win_pcts else []

        day_data = []
        for ps_id, player_id, team_id, float_shares, status, birthdate, ext_id in all_players:
            stats = game_stats_by_player.get(ps_id, [])
            games_before = [s for s in stats if s["game_date"] <= games_cutoff]
            n_games = len(games_before)

            prior_raw = prior_avgs.get(ext_id, None)

            if n_games == 0 and prior_raw is None:
                continue

            if n_games > 0:
                season_avg = {k: sum(g[k] for g in games_before) / n_games for k in STAT_KEYS}
                season_raw = calculate_raw_perf(*(season_avg[k] for k in STAT_KEYS))
            else:
                season_raw = 0.0

            if n_games > 0:
                recent_games = games_before[-RECENT_WINDOW:]
                recent_n = len(recent_games)
                recent_avg = {k: sum(g[k] for g in recent_games) / recent_n for k in STAT_KEYS}
                recent_raw = calculate_raw_perf(*(recent_avg[k] for k in STAT_KEYS))
                blended_raw = (1 - RECENT_WEIGHT) * season_raw + RECENT_WEIGHT * recent_raw
            else:
                blended_raw = 0.0

            if prior_raw is not None and n_games < PRIOR_BLEND_GAMES:
                prior_weight = 1.0 - (n_games / PRIOR_BLEND_GAMES)
                if n_games == 0:
                    blended_raw = prior_raw
                else:
                    blended_raw = (1 - prior_weight) * blended_raw + prior_weight * prior_raw

            perf_score = max(0.5, blended_raw)
            day_data.append((ps_id, player_id, team_id, float_shares, status, birthdate,
                            ext_id, perf_score, blended_raw, games_before, n_games, prior_raw))

        for (ps_id, player_id, team_id, float_shares, status, birthdate, ext_id,
             perf_score, blended_raw, games_before, n_games, prior_raw) in day_data:
            normalized = perf_score / 100.0
            base_price = (normalized ** PRICE_EXPONENT) * PRICE_CEILING

            # Age multiplier based on player's own performance (0-100), not relative to league
            age_perf_score = min(100.0, blended_raw)
            age_mult = get_age_multiplier(birthdate, age_perf_score)

            if n_games > 0:
                last_game = max(s["game_date"] for s in games_before)
                days_since = (trade_date - last_game).days
                consecutive_missed = max(0, (days_since - 2) // 2)
            elif prior_raw is not None:
                days_into = (trade_date - start).days
                consecutive_missed = max(0, days_into // 2)
            else:
                consecutive_missed = 0

            injury_mult = get_injury_mult(consecutive_missed)
            win_pct = team_win_pcts.get(team_id, 0.5)
            win_pct_mult = get_win_pct_multiplier(win_pct, all_win_pcts)

            raw_score = base_price * age_mult * injury_mult * win_pct_mult
            price = round(raw_score, 2)
            if price < 0.01:
                price = 0.01
            mcap = round(price * float_shares, 2)

            prev_price = prev_prices.get(ps_id)
            change_pct = None
            if prev_price and prev_price > 0:
                # Use raw_score (not rounded price) so small changes are visible when rounding makes price == prev_price
                change_pct = round((raw_score - prev_price) / prev_price, 4)

            rows_to_insert.append((
                ps_id, trade_date, round(float(perf_score), 4), float(age_mult),
                round(float(win_pct_mult), 4), round(float(injury_mult), 4), round(float(raw_score), 4), float(price),
                float(mcap), float(prev_price) if prev_price else None,
                float(change_pct) if change_pct is not None else None,
            ))
            prev_prices[ps_id] = price
            price_count += 1

        if rows_to_insert:
            with conn.cursor() as cur:
                execute_values(
                    cur,
                    """INSERT INTO price_history
                           (player_season_id, trade_date, perf_score, age_mult, win_pct_mult,
                            salary_eff_mult, raw_score, price, market_cap, prev_price, change_pct)
                       VALUES %s
                       ON CONFLICT (player_season_id, trade_date) DO UPDATE SET
                           perf_score = EXCLUDED.perf_score, age_mult = EXCLUDED.age_mult,
                           win_pct_mult = EXCLUDED.win_pct_mult, salary_eff_mult = EXCLUDED.salary_eff_mult,
                           raw_score = EXCLUDED.raw_score, price = EXCLUDED.price,
                           market_cap = EXCLUDED.market_cap, prev_price = EXCLUDED.prev_price,
                           change_pct = EXCLUDED.change_pct""",
                    rows_to_insert,
                    page_size=500,
                )

        if (td_idx + 1) % 10 == 0:
            conn.commit()
            log.info("  ...%d / %d trading days computed", td_idx + 1, len(trade_days))

    conn.commit()
    log.info("Inserted %d price history rows", price_count)


def compute_prices_for_single_date(
    conn,
    season_id: int,
    prior_avgs: dict,
    season_start: date,
    trade_date: date,
    prev_prices: dict,
) -> list[dict]:
    """
    Compute prices for a single trade date. Same methodology as compute_historical_prices.
    Returns list of dicts for update_market to insert.
    """
    with conn.cursor() as cur:
        cur.execute(
            """SELECT ps.id, ps.player_id, ps.team_id, ps.float_shares, ps.status,
                      p.birthdate, p.external_id
               FROM player_seasons ps JOIN players p ON ps.player_id = p.id
               WHERE ps.season_id = %s AND ps.status NOT IN ('delisting', 'delisted')""",
            (season_id,),
        )
        all_players = cur.fetchall()

    if not all_players:
        return []

    game_stats_by_player = {}
    with conn.cursor() as cur:
        cur.execute(
            """SELECT player_season_id, game_date,
                      pts, fgm, fga, ftm, fta, fg3m, fg3a,
                      oreb, dreb, ast, stl, blk, tov
               FROM game_stats gs JOIN player_seasons ps ON gs.player_season_id = ps.id
               WHERE ps.season_id = %s ORDER BY game_date""",
            (season_id,),
        )
        for row in cur.fetchall():
            ps_id = row[0]
            if ps_id not in game_stats_by_player:
                game_stats_by_player[ps_id] = []
            game_stats_by_player[ps_id].append({
                "game_date": row[1],
                "pts": float(row[2]), "fgm": float(row[3]), "fga": float(row[4]),
                "ftm": float(row[5]), "fta": float(row[6]),
                "fg3m": float(row[7]), "fg3a": float(row[8]),
                "oreb": float(row[9]), "dreb": float(row[10]),
                "ast": float(row[11]), "stl": float(row[12]),
                "blk": float(row[13]), "tov": float(row[14]),
            })

    # Use games *before* trade_date so price = "as of market open" (previous day's close).
    # Daily change = impact of previous day's games.
    games_cutoff = trade_date - timedelta(days=1) if trade_date else trade_date
    team_win_pcts = get_team_win_pcts_as_of_date(conn, season_id, games_cutoff)
    all_win_pcts = list(team_win_pcts.values()) if team_win_pcts else []

    day_data = []
    for ps_id, player_id, team_id, float_shares, status, birthdate, ext_id in all_players:
        stats = game_stats_by_player.get(ps_id, [])
        games_before = [s for s in stats if s["game_date"] <= games_cutoff]
        n_games = len(games_before)

        prior_raw = prior_avgs.get(ext_id, None)

        if n_games == 0 and prior_raw is None:
            continue

        if n_games > 0:
            season_avg = {k: sum(g[k] for g in games_before) / n_games for k in STAT_KEYS}
            season_raw = calculate_raw_perf(*(season_avg[k] for k in STAT_KEYS))
        else:
            season_raw = 0.0

        if n_games > 0:
            recent_games = games_before[-RECENT_WINDOW:]
            recent_n = len(recent_games)
            recent_avg = {k: sum(g[k] for g in recent_games) / recent_n for k in STAT_KEYS}
            recent_raw = calculate_raw_perf(*(recent_avg[k] for k in STAT_KEYS))
            blended_raw = (1 - RECENT_WEIGHT) * season_raw + RECENT_WEIGHT * recent_raw
        else:
            blended_raw = 0.0

        if prior_raw is not None and n_games < PRIOR_BLEND_GAMES:
            prior_weight = 1.0 - (n_games / PRIOR_BLEND_GAMES)
            if n_games == 0:
                blended_raw = prior_raw
            else:
                blended_raw = (1 - prior_weight) * blended_raw + prior_weight * prior_raw

        perf_score = max(0.5, blended_raw)
        day_data.append((ps_id, player_id, team_id, float_shares, status, birthdate,
                        ext_id, perf_score, blended_raw, games_before, n_games, prior_raw))

    results = []
    for (ps_id, player_id, team_id, float_shares, status, birthdate, ext_id,
         perf_score, blended_raw, games_before, n_games, prior_raw) in day_data:
        normalized = perf_score / 100.0
        base_price = (normalized ** PRICE_EXPONENT) * PRICE_CEILING

        # Age multiplier based on player's own performance (0-100), not relative to league
        age_perf_score = min(100.0, blended_raw)
        age_mult = get_age_multiplier(birthdate, age_perf_score)

        if n_games > 0:
            last_game = max(s["game_date"] for s in games_before)
            days_since = (trade_date - last_game).days
            consecutive_missed = max(0, (days_since - 2) // 2)
        elif prior_raw is not None:
            days_into = (trade_date - season_start).days
            consecutive_missed = max(0, days_into // 2)
        else:
            consecutive_missed = 0

        injury_mult = get_injury_mult(consecutive_missed)
        win_pct = team_win_pcts.get(team_id, 0.5)
        win_pct_mult = get_win_pct_multiplier(win_pct, all_win_pcts)

        raw_score = base_price * age_mult * injury_mult * win_pct_mult
        price = round(raw_score, 2)
        if price < 0.01:
            price = 0.01
        mcap = round(price * float_shares, 2)

        prev_price = prev_prices.get(ps_id)
        change_pct = None
        if prev_price and prev_price > 0:
            # Use raw_score (not rounded price) so small changes are visible when rounding makes price == prev_price
            change_pct = round((raw_score - prev_price) / prev_price, 4)

        results.append({
            "player_season_id": ps_id,
            "trade_date": trade_date,
            "perf_score": round(float(perf_score), 4),
            "age_mult": float(age_mult),
            "win_pct_mult": round(float(win_pct_mult), 4),
            "salary_eff_mult": round(float(injury_mult), 4),
            "raw_score": round(float(raw_score), 4),
            "price": float(price),
            "market_cap": float(mcap),
            "prev_price": float(prev_price) if prev_price else None,
            "change_pct": float(change_pct) if change_pct is not None else None,
        })

    return results
