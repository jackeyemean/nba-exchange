import json
import logging
from datetime import date

from config import get_redis

log = logging.getLogger(__name__)

MAX_CONSTITUENT_WEIGHT = 0.12

POSITION_GROUPS = {
    "Guards": ["Guard", "G", "PG", "SG", "G-F"],
    "Wings": ["Forward", "F", "SF", "F-G", "F-C", "GF"],
    "Bigs": ["Center", "C", "PF", "C-F"],
}


def setup_default_indexes(conn, season_id: int):
    log.info("Setting up default indexes for season %d", season_id)

    _upsert_index(conn, "NBA League Index", "league", "Cap-weighted index of all active players")

    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM teams")
        teams = cur.fetchall()

    for team_id, team_name in teams:
        _upsert_index(conn, f"{team_name} Index", "team",
                       f"Cap-weighted index for {team_name}", team_id=team_id)

    for group_name in POSITION_GROUPS:
        _upsert_index(conn, f"{group_name} Index", "position",
                       f"Cap-weighted index for {group_name.lower()}")

    _upsert_index(conn, "Momentum Index", "momentum",
                   "Top performers by recent price change")

    conn.commit()
    log.info("Default indexes created")


def _upsert_index(conn, name: str, index_type: str, description: str, team_id: int | None = None):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO indexes (name, index_type, description, team_id)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description
            RETURNING id
            """,
            (name, index_type, description, team_id),
        )
        return cur.fetchone()[0]


def _cap_weights(raw_weights: dict[int, float]) -> dict[int, float]:
    """Apply iterative capping at MAX_CONSTITUENT_WEIGHT."""
    weights = dict(raw_weights)
    for _ in range(20):
        total = sum(weights.values())
        if total == 0:
            return weights
        normed = {k: v / total for k, v in weights.items()}
        excess = {k: v for k, v in normed.items() if v > MAX_CONSTITUENT_WEIGHT}
        if not excess:
            return normed
        capped_total = MAX_CONSTITUENT_WEIGHT * len(excess)
        remaining_keys = [k for k in normed if k not in excess]
        remaining_total = sum(normed[k] for k in remaining_keys)
        if remaining_total == 0:
            return normed
        scale = (1.0 - capped_total) / remaining_total
        weights = {}
        for k in excess:
            weights[k] = MAX_CONSTITUENT_WEIGHT
        for k in remaining_keys:
            weights[k] = normed[k] * scale
    total = sum(weights.values())
    return {k: v / total for k, v in weights.items()} if total > 0 else weights


def rebalance_indexes(conn, season_id: int, trade_date: date):
    log.info("Rebalancing indexes for season %d on %s", season_id, trade_date)

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ph.player_season_id, ph.price, ph.market_cap, ph.change_pct,
                   ps.team_id, p.position
            FROM price_history ph
            JOIN player_seasons ps ON ph.player_season_id = ps.id
            JOIN players p ON ps.player_id = p.id
            WHERE ph.trade_date = %s AND ps.season_id = %s
              AND ps.status NOT IN ('delisting', 'delisted')
            """,
            (trade_date, season_id),
        )
        price_rows = cur.fetchall()

    if not price_rows:
        log.warning("No price data for %s, skipping rebalance", trade_date)
        return

    all_prices = {}
    for row in price_rows:
        all_prices[row[0]] = {
            "price": float(row[1]), "market_cap": float(row[2]),
            "change_pct": float(row[3]) if row[3] else 0.0,
            "team_id": row[4], "position": row[5] or "",
        }

    with conn.cursor() as cur:
        cur.execute("SELECT id, name, index_type, team_id FROM indexes")
        indexes = cur.fetchall()

    prev_levels = {}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT index_id, level FROM index_history
            WHERE trade_date = (SELECT MAX(trade_date) FROM index_history WHERE trade_date < %s)
            """,
            (trade_date,),
        )
        for row in cur.fetchall():
            prev_levels[row[0]] = float(row[1])

    index_results = []

    for idx_id, idx_name, idx_type, idx_team_id in indexes:
        constituents = _select_constituents(all_prices, idx_type, idx_team_id, idx_name)
        if not constituents:
            continue

        raw_weights = {ps_id: all_prices[ps_id]["market_cap"] for ps_id in constituents}
        capped = _cap_weights(raw_weights)

        for ps_id, weight in capped.items():
            _upsert_constituent(conn, idx_id, ps_id, weight)

        weighted_return = sum(
            capped[ps_id] * all_prices[ps_id]["change_pct"]
            for ps_id in capped
        )

        prev_level = prev_levels.get(idx_id, 1000.0)
        level = prev_level * (1.0 + weighted_return)

        change_pct = (level - prev_level) / prev_level if prev_level > 0 else None

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO index_history (index_id, trade_date, level, prev_level, change_pct)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (index_id, trade_date) DO UPDATE SET
                    level = EXCLUDED.level, prev_level = EXCLUDED.prev_level,
                    change_pct = EXCLUDED.change_pct
                """,
                (idx_id, trade_date, round(level, 4), round(prev_level, 4),
                 round(change_pct, 4) if change_pct is not None else None),
            )

        index_results.append({
            "index_id": idx_id, "name": idx_name,
            "level": round(level, 4), "change_pct": round(change_pct, 4) if change_pct is not None else None,
        })

    conn.commit()
    log.info("Rebalanced %d indexes", len(index_results))

    try:
        r = get_redis()
        r.publish("indexes", json.dumps(index_results))
        log.info("Published index data to Redis")
    except Exception:
        log.exception("Failed to publish index data to Redis")


def _select_constituents(all_prices: dict, idx_type: str, team_id: int | None,
                         index_name: str = "") -> list[int]:
    if idx_type == "league":
        return list(all_prices.keys())

    if idx_type == "team" and team_id is not None:
        return [ps_id for ps_id, info in all_prices.items() if info["team_id"] == team_id]

    if idx_type == "position":
        target_group = None
        name_lower = index_name.lower()
        for group in POSITION_GROUPS:
            if group.lower() in name_lower:
                target_group = group
                break
        if not target_group:
            return []
        valid_positions = POSITION_GROUPS[target_group]
        return [ps_id for ps_id, info in all_prices.items() if info["position"] in valid_positions]

    if idx_type == "momentum":
        sorted_by_change = sorted(all_prices.items(), key=lambda x: x[1]["change_pct"], reverse=True)
        top_n = max(1, len(sorted_by_change) // 10)
        return [ps_id for ps_id, _ in sorted_by_change[:top_n]]

    return []


def _upsert_constituent(conn, index_id: int, player_season_id: int, weight: float):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO index_constituents (index_id, player_season_id, weight, updated_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (index_id, player_season_id) DO UPDATE SET
                weight = EXCLUDED.weight, updated_at = NOW()
            """,
            (index_id, player_season_id, round(weight, 6)),
        )


