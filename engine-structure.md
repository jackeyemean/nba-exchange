# Engine Structure

The engine is a **Python** data pipeline that ingests NBA stats, computes stock prices, assigns tiers, and manages indexes. It populates PostgreSQL.

**Most important script:** `scripts/restart_simulation.py` – Full market reset. Simulates prior 2 seasons with uniform shares, assigns tiers from ranking, then simulates current season with tier-based shares.

---

## Directory Layout

```
engine/
├── constants.py                 # ★ Single source of truth for all constants
├── config.py                    # Env vars, DB connection
├── utils/
│   ├── api.py                  # safe_request (rate limit, retry)
│   └── dates.py                # trading_days_in_range, game_dates_to_ingest
├── db/
│   ├── seasons.py              # ensure_season, get_season_by_label, ensure_season_with_dates
│   ├── prices.py               # insert_price_history, get_prev_prices
│   └── rankings.py             # get_end_of_season_ranking
├── formulas/
│   ├── raw_perf.py             # calculate_raw_perf (13-stat formula)
│   ├── multipliers.py          # get_age_multiplier, get_win_pct_multiplier, get_injury_mult
│   └── compute.py              # compute_historical_prices, compute_prices_for_single_date
├── ingestion/
│   ├── nba.py                  # sync_teams, sync_players, sync_game_logs, sync_standings
│   └── game_stats.py           # sync_incremental_game_stats (LeagueGameLog, date-filtered)
├── tiers/
│   ├── assignment.py           # assign_tiers_by_perf, assign_tiers_from_ranking
│   └── year0.py                # build_year0_tier_fn, apply_year0_tiers_from_prices, rookie_tier_from_pick
├── indexes/
│   └── calculator.py           # setup_default_indexes, rebalance_indexes
├── scripts/
│   ├── restart_simulation.py   # ★ Full market reset
│   ├── backfill.py             # Full backfill for a season
│   └── update_market.py        # Daily price update (run at market open)
├── requirements.txt
└── Dockerfile
```

**Run (from `engine/`):**
- `python scripts/restart_simulation.py` — bootstrap/reset market
- `python scripts/backfill.py --season 2025-26` — full backfill for a season
- `python scripts/update_market.py --season 2025-26` — daily at 6:00 AM ET (market open)

---

## restart_simulation.py (Core Script)

**Purpose:** Full market reset. Simulate 2 prior seasons with uniform shares, rank players by end-of-season price, assign tiers, then simulate current season with tier-based shares.

### Flow

| Phase | Description |
|-------|-------------|
| **Phase 1** | Simulate 2023-24 with uniform 5M shares per player |
| **Phase 2** | Simulate 2024-25 with uniform 5M shares |
| **Phase 3** | Rank players by price at end of 2024-25; assign tiers by cutoff |
| **Phase 4** | Simulate 2025-26 with tier-based shares; rookies by draft position |
| **Phase 5** | Initialize indexes (constituents + history) for 2025-26 |

### Tier Cutoffs (from ranking)

| Tier | Rank |
|------|------|
| magnificent_7 | Top 7 |
| blue_chip | 8–40 |
| growth | 41–150 |
| mid_cap | 151–250 |
| penny_stock | Rest |

### Rookie Tiers (by draft pick)

| Pick | Tier |
|------|------|
| 1–14 (lottery) | growth |
| 15–39 | mid_cap |
| 40+ | penny_stock |

---

## Stock Price Formulas

### Historical & Single-Date (`formulas.compute`)

- `compute_historical_prices` — used by `restart_simulation` and `backfill`
- `compute_prices_for_single_date` — used by `update_market`
- Uses full game stats: pts, fgm, fga, ftm, fta, fg3m, fg3a, oreb, dreb, ast, stl, blk, tov

**Raw perf formula (13 stats):**

```
raw = (pts×1) + (fgm×1) + (fgmi×-1) + (ftm×1) + (ftmi×-1)
    + (fg3m×1) + (oreb×1) + (dreb×1) + (ast×2)
    + (stl×4) + (blk×4) + (tov×-2)
```

- **Prior-season blend:** First 10 games blend with prior-season averages
- **Recent-form:** Last 15 games weighted 20%
- **Base price:** `(perf/100)^2.5 * 275` (cap $275)
- **Multipliers:** age, win%, injury
- `market_cap = price * float_shares`

### Shared Multipliers

| Multiplier | Logic |
|------------|-------|
| **Age** | Prime 28–32; youth/aging penalties; caps 0.5–2.0 |
| **Win%** | 0.90 (worst) to 1.15 (best) by league rank |
| **Injury** | `get_injury_mult(consecutive_missed)` – curve over 35 games, floor 0.70 |

### Float Shares by Tier

| Tier | Float Shares |
|------|-------------|
| magnificent_7 | 12,000,000 |
| blue_chip | 8,000,000 |
| growth | 6,000,000 |
| mid_cap | 5,000,000 |
| penny_stock | 3,000,000 |

---

## Data Flow

```
NBA API (nba_api) → ingestion.nba / ingestion.game_stats
                    ↓
scripts/backfill: sync_teams → sync_players → sync_game_logs → sync_standings
             → formulas.compute.compute_historical_prices → tiers.year0.apply_year0_tiers_from_prices
                    ↓
scripts/restart_simulation: same sync + compute for prior seasons (uniform shares)
             → assign tiers from ranking → simulate current season (tier shares)
             → indexes.calculator (setup_default_indexes, rebalance_indexes)
                    ↓
scripts/update_market: sync_incremental_game_stats (date-by-date) → sync_standings → compute_prices_for_single_date
             → db.prices.insert_price_history → rebalance_indexes
                    ↓
PostgreSQL (price_history, index_history, etc.)
                    ↓
Backend API → Frontend
```

---

## Configuration (Environment)

| Variable | Description |
|----------|-------------|
| `ENGINE_DATABASE_URL` / `DATABASE_URL` | PostgreSQL URL |
| `SCALING_FACTOR` | Daily price scaling (default 2.08) |

---

## Module Roles

| Module | Role |
|--------|------|
| `constants.py` | All shared constants (tiers, float shares, formula params, injury curve, season configs) |
| `config.py` | Environment variables and DB connection helpers |
| `utils.api` | safe_request for nba_api (rate limit, retry) |
| `utils.dates` | trading_days_in_range, game_dates_to_ingest |
| `db.seasons` | ensure_season, get_season_by_label, ensure_season_with_dates |
| `db.prices` | insert_price_history, get_prev_prices |
| `db.rankings` | get_end_of_season_ranking |
| `formulas.raw_perf` | calculate_raw_perf |
| `formulas.multipliers` | get_age_multiplier, get_win_pct_multiplier, get_injury_mult |
| `formulas.compute` | compute_historical_prices, compute_prices_for_single_date |
| `ingestion.nba` | NBA API sync (teams, players, game logs, standings, prior averages) |
| `ingestion.game_stats` | Date-specific game stats for daily updates |
| `tiers.assignment` | assign_tiers_by_perf, assign_tiers_from_ranking |
| `tiers.year0` | build_year0_tier_fn, apply_year0_tiers_from_prices, rookie_tier_from_pick |
| `indexes.calculator` | setup_default_indexes, rebalance_indexes |
