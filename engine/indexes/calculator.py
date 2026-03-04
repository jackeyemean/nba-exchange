import logging
from datetime import date

log = logging.getLogger(__name__)

POSITION_GROUPS = {
    "Guards": ["Guard", "G", "PG", "SG", "G-F"],
    "Wings": ["Forward", "F", "SF", "F-G", "F-C", "GF"],
    "Bigs": ["Center", "C", "PF", "C-F"],
}


def setup_default_indexes(conn, season_id: int):
    log.info("Setting up default indexes for season %d", season_id)

    # Market-cap-ranked indexes (cap-weighted, top N by market cap)
    _upsert_index(conn, "S&P 500", "sp500", "Cap-weighted index of top 500 players by market cap", ticker="INX")
    _upsert_index(conn, "S&P 100", "sp100", "Cap-weighted index of top 100 players by market cap", ticker="OEX")
    _upsert_index(conn, "Dow Jones Industrial Average", "djia", "Cap-weighted index of top 30 players by market cap", ticker="DJIA")

    # Tier-based indexes (all players in tier, cap-weighted)
    _upsert_index(conn, "Magnificent 7", "tier_mag7", "Cap-weighted index of all Magnificent 7 tier players", ticker="MAG7")
    _upsert_index(conn, "Blue Chips", "tier_bluechip", "Cap-weighted index of all Blue Chip tier players", ticker="BLUE")
    _upsert_index(conn, "Renaissance IPO Index", "ipo", "Cap-weighted index of all rookies in the current season", ticker="IPO")

    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM teams")
        teams = cur.fetchall()

    for team_id, team_name in teams:
        _upsert_index(conn, f"{team_name} Index", "team",
                       f"Cap-weighted index for {team_name}", team_id=team_id)

    for group_name in POSITION_GROUPS:
        _upsert_index(conn, f"{group_name} Index", "position",
                       f"Cap-weighted index for {group_name.lower()}")

    # Remove momentum index if it exists (causes level overflow from extreme returns)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM indexes WHERE index_type = 'momentum'"
        )
        momentum_ids = [row[0] for row in cur.fetchall()]
        for idx_id in momentum_ids:
            cur.execute("DELETE FROM index_constituents WHERE index_id = %s", (idx_id,))
            cur.execute("DELETE FROM index_history WHERE index_id = %s", (idx_id,))
            cur.execute("DELETE FROM indexes WHERE id = %s", (idx_id,))
        if momentum_ids:
            log.info("Removed %d momentum index(es)", len(momentum_ids))

    conn.commit()
    log.info("Default indexes created")


def _upsert_index(conn, name: str, index_type: str, description: str, team_id: int | None = None, ticker: str | None = None):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO indexes (name, index_type, description, team_id, ticker)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE SET
                index_type = EXCLUDED.index_type,
                description = EXCLUDED.description,
                team_id = COALESCE(EXCLUDED.team_id, indexes.team_id),
                ticker = COALESCE(EXCLUDED.ticker, indexes.ticker)
            RETURNING id
            """,
            (name, index_type, description, team_id, ticker),
        )
        return cur.fetchone()[0]


def _cap_weights(raw_weights: dict[int, float]) -> dict[int, float]:
    """Compute cap-weighted weights (no max cap)."""
    total = sum(raw_weights.values())
    if total == 0:
        return raw_weights
    return {k: v / total for k, v in raw_weights.items()}


def _get_rookie_external_ids(conn, season_id: int) -> set[str]:
    """Fetch draft class for the season's draft year; returns set of external_ids."""
    with conn.cursor() as cur:
        cur.execute("SELECT label FROM seasons WHERE id = %s", (season_id,))
        row = cur.fetchone()
    if not row:
        return set()
    draft_year = int(str(row[0]).split("-")[0])
    try:
        from nba_api.stats.endpoints import DraftHistory
        import time
        time.sleep(0.5)  # Rate limit
        resp = DraftHistory(season_year_nullable=draft_year)
        df = resp.get_data_frames()[0]
        return {str(r["PERSON_ID"]) for _, r in df.iterrows()}
    except Exception as e:
        log.warning("Failed to fetch draft history for IPO index: %s", e)
        return set()


def rebalance_indexes(conn, season_id: int, trade_date: date):
    log.info("Rebalancing indexes for season %d on %s", season_id, trade_date)

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ph.player_season_id, ph.price, ph.market_cap, ph.change_pct,
                   ps.team_id, p.position, ps.tier::text, p.external_id
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
            "team_id": row[4], "position": row[5] or "", "tier": row[6] or "",
            "external_id": str(row[7]) if row[7] else "",
        }

    rookie_external_ids = _get_rookie_external_ids(conn, season_id)

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
        constituents = _select_constituents(all_prices, idx_type, idx_team_id, idx_name, rookie_external_ids)
        if not constituents:
            continue

        raw_weights = {ps_id: all_prices[ps_id]["market_cap"] for ps_id in constituents}
        capped = _cap_weights(raw_weights)

        # Remove constituents no longer in the index (e.g. dropped from top 500)
        constituent_ids = list(capped.keys())
        with conn.cursor() as cur:
            if constituent_ids:
                cur.execute(
                    "DELETE FROM index_constituents WHERE index_id = %s AND player_season_id != ALL(%s)",
                    (idx_id, constituent_ids),
                )
            else:
                cur.execute("DELETE FROM index_constituents WHERE index_id = %s", (idx_id,))

        for ps_id, weight in capped.items():
            _upsert_constituent(conn, idx_id, ps_id, weight)

        weighted_return = sum(
            capped[ps_id] * all_prices[ps_id]["change_pct"]
            for ps_id in capped
        )

        prev_level = prev_levels.get(idx_id, 1000.0)
        level = prev_level * (1.0 + weighted_return)

        # Cap level to prevent NUMERIC(12,4) overflow (max < 10^8)
        MAX_LEVEL = 99_999_999.99
        level = min(max(level, 0.0001), MAX_LEVEL)
        prev_level = min(max(prev_level, 0.0001), MAX_LEVEL)

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


# Cap limits for market-cap-ranked indexes
SP500_CAP = 500
SP100_CAP = 100
DJIA_CAP = 30


def _select_constituents(all_prices: dict, idx_type: str, team_id: int | None,
                         index_name: str = "", rookie_external_ids: set[str] | None = None) -> list[int]:
    # Market-cap-ranked: top N by market cap (cap-weighted)
    if idx_type == "sp500":
        sorted_ids = sorted(all_prices.keys(), key=lambda k: all_prices[k]["market_cap"], reverse=True)
        return sorted_ids[:SP500_CAP]
    if idx_type == "sp100":
        sorted_ids = sorted(all_prices.keys(), key=lambda k: all_prices[k]["market_cap"], reverse=True)
        return sorted_ids[:SP100_CAP]
    if idx_type == "djia":
        sorted_ids = sorted(all_prices.keys(), key=lambda k: all_prices[k]["market_cap"], reverse=True)
        return sorted_ids[:DJIA_CAP]

    # Tier-based: all players in tier (cap-weighted)
    if idx_type == "tier_mag7":
        return [ps_id for ps_id, info in all_prices.items() if info.get("tier") == "magnificent_7"]
    if idx_type == "tier_bluechip":
        return [ps_id for ps_id, info in all_prices.items() if info.get("tier") == "blue_chip"]
    # IPO index: all rookies (drafted in current season's draft year)
    if idx_type == "ipo":
        rookies = rookie_external_ids or set()
        return [ps_id for ps_id, info in all_prices.items() if info.get("external_id", "") in rookies]

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


