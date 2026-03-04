# PlayerExchange

A fan simulation stock exchange where basketball players are tradable assets. Prices are derived from real game stats using a deterministic formula. No real money involved.

**Disclaimer:** Fan simulation only. Not affiliated with any professional league. No real monetary value.

## Architecture

```
backend/    → Go API server (auth, trading, portfolio, leaderboard)
engine/     → Python data ingestion, pricing worker, index calculator
web/        → Next.js frontend with light/dark mode
migrations/ → PostgreSQL schema
```

### Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js, TypeScript, Tailwind CSS, Recharts |
| API / Trading | Go (Gin), PostgreSQL |
| Ingestion | Python, nba_api, basketball_reference_web_scraper |
| Pricing | Python (scheduled worker) |

## Pricing Formula

Prices update at market open (6:00 AM ET) based on the previous day's games.

```
Performance Score = (PTS×2.0) + (AST×1.5) + (REB×1.2) + (STL×2.0) + (BLK×1.5) - (TOV×1.8) + (TS%×20)
→ Normalized to 0-100 across all players

Final Price = (PerfScore × AgeMult × WinPctMult) × ScalingFactor
Market Cap  = Price × FloatShares
```

## Market Rules

- **Hours:** 6:00 AM – 6:00 PM ET, weekdays only
- **Orders:** Market orders (instant fill at day's price)
- **Currency:** Virtual only ($100,000 starting balance)
- **Protections:** Rate limits (100 req/min), abuse guards (30 orders/min per user)

## Quick Start

### Prerequisites

- Go 1.23+
- Python 3.12+
- Node.js 20+
- Docker (for PostgreSQL)

### 1. Start infrastructure

```bash
docker compose up -d postgres
```

### 2. Run database migrations

```bash
psql $DATABASE_URL -f migrations/001_initial_schema.up.sql
psql $DATABASE_URL -f migrations/002_game_stats_wl.up.sql
psql $DATABASE_URL -f migrations/003_index_history_precision.up.sql
psql $DATABASE_URL -f migrations/004_index_ticker_and_types.up.sql
psql $DATABASE_URL -f migrations/005_renaissance_ipo_index.up.sql
```

### 3. Set up environment

```bash
cp .env.example .env
# Edit .env with your values
```

### 4. Start the Python engine

```bash
cd engine
pip install -r requirements.txt
python main.py sync-all --season 2025-26
python main.py tier-bootstrap   # Assigns tiers from prior-season ranking, computes prices, initializes indexes
# Or if you skip tier-bootstrap and use sync-all only:
python main.py price --season 2025-26
python main.py rebalance --season 2025-26
```

**Recommended:** Run `tier-bootstrap` after sync-all. It assigns performance-based tiers (from prior-season ranking), computes historical prices, and initializes indexes. Tiers are **never** overwritten by sync-all—`sync_players` preserves existing tiers and only updates team/roster.

### 5. Start the Go API

```bash
cd backend
go mod tidy
go run cmd/api/main.go
```

### 6. Start the frontend

```bash
cd web
npm install
npm run dev
```

## API Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | /api/auth/register | No | Create account |
| POST | /api/auth/login | No | Login |
| GET | /api/players | No | List all players with prices |
| GET | /api/players/:id | No | Player detail + price history |
| POST | /api/orders | Yes | Place buy/sell order |
| GET | /api/portfolio | Yes | User portfolio |
| GET | /api/orders | Yes | Order history |
| GET | /api/trades | Yes | Trade history |
| GET | /api/indexes | No | List all indexes |
| GET | /api/indexes/:id | No | Index detail + constituents |
| GET | /api/leaderboard | No | Rankings by total value |

## Engine CLI

```bash
python main.py sync-all --season 2025-26     # Full data sync (teams, players, standings, index definitions)
python main.py tier-bootstrap                # Tiers from prior-season ranking + prices + index init
python main.py sync-standings --season 2025-26  # Standings only (for daily schedule)
python main.py ingest --season 2025-26 --date 2025-12-01  # Single date
python main.py price --season 2025-26         # Run pricing (updates player prices)
python main.py rebalance --season 2025-26     # Rebalance indexes (constituents + history for today)
python main.py schedule --season 2025-26      # Daily scheduler (8am ET)
```

**Indexes:** `sync-all` creates index definitions. `tier-bootstrap` populates constituents and history from price data. The daily `schedule` runs `price` then `rebalance` to keep indexes in sync with the market.

**Tiers:** Only `tier-bootstrap` assigns tiers (performance-based from prior-season ranking). `sync_players` never overwrites tiers—it preserves existing tier/float_shares and only updates team_id for roster changes. New players get `penny_stock` until the next tier-bootstrap.

## Market Automation

The engine runs a daily job at **8:00 AM ET** that:

1. Ingests game stats (yesterday, or Fri–Sun if Monday)
2. Syncs standings
3. Runs pricing (updates all player prices)
4. Rebalances indexes

### Option 1: Run as a long-lived process

```bash
cd engine
python main.py schedule --season 2025-26
```

Keeps running and triggers the job daily. Use `nohup`, `screen`, or `tmux` for background execution.

### Option 2: Cron (Linux/macOS)

Use a wrapper script that replicates the schedule logic (Monday = ingest Fri–Sun; other weekdays = ingest yesterday). Example `run_daily.sh`:

```bash
#!/bin/bash
cd /path/to/nba-exchange/engine
SEASON="2025-26"
TODAY=$(date +%Y-%m-%d)
if [ "$(date +%u)" = "1" ]; then
  for d in 3 2 1; do
    D=$(date -d "$TODAY - ${d} days" +%Y-%m-%d)
    python main.py ingest --season "$SEASON" --date "$D" || true
  done
else
  YESTERDAY=$(date -d "$TODAY - 1 day" +%Y-%m-%d)
  python main.py ingest --season "$SEASON" --date "$YESTERDAY" || true
fi
python main.py sync-standings --season "$SEASON"
python main.py price --season "$SEASON"
python main.py rebalance --season "$SEASON"
```

Then add to crontab (8:00 AM ET weekdays): `0 8 * * 1-5 /path/to/run_daily.sh`

**Simpler:** Run `python main.py schedule --season 2025-26` as a daemon (Option 1) instead of cron.

### Option 3: systemd (Linux)

Create `/etc/systemd/system/nba-exchange-engine.service`:

```ini
[Unit]
Description=NBA Exchange Engine Scheduler
After=network.target postgresql.service

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/nba-exchange/engine
ExecStart=/usr/bin/python3 main.py schedule --season 2025-26
Restart=always
RestartSec=60
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable nba-exchange-engine
sudo systemctl start nba-exchange-engine
```
