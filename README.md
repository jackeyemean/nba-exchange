# PlayerExchange

A fan simulation stock exchange where basketball players are tradable assets. Prices are derived from real game stats using a deterministic formula. No real money involved.

**Disclaimer:** Fan simulation only. Not affiliated with any professional league. No real monetary value.

## Architecture

```
backend/    → Go API server, execution engine, WebSocket hub
engine/     → Python data ingestion, pricing worker, index calculator
web/        → Next.js frontend with light/dark mode
migrations/ → PostgreSQL schema
```

### Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js, TypeScript, Tailwind CSS, Recharts |
| API / Trading | Go (Gin), PostgreSQL, Redis |
| WebSocket | Go (gorilla/websocket), Redis Pub/Sub |
| Ingestion | Python, nba_api, basketball_reference_web_scraper |
| Pricing | Python (scheduled worker) |

## Pricing Formula

Prices update at market open (9:30 AM ET) based on the previous day's games.

```
Performance Score = (PTS×2.0) + (AST×1.5) + (REB×1.2) + (STL×2.0) + (BLK×1.5) - (TOV×1.8) + (TS%×20)
→ Normalized to 0-100 across all players

Final Price = (PerfScore × AgeMult × WinPctMult) × ScalingFactor
Market Cap  = Price × FloatShares
```

## Market Rules

- **Hours:** 9:30 AM – 5:00 PM ET, weekdays only
- **Orders:** Market orders (instant fill at day's price)
- **Currency:** Virtual only ($100,000 starting balance)
- **Protections:** Rate limits (100 req/min), abuse guards (30 orders/min per user)

## Quick Start

### Prerequisites

- Go 1.23+
- Python 3.12+
- Node.js 20+
- Docker (for PostgreSQL and Redis)

### 1. Start infrastructure

```bash
docker compose up -d postgres redis
```

### 2. Run database migrations

```bash
psql $DATABASE_URL -f migrations/001_initial_schema.up.sql
psql $DATABASE_URL -f migrations/002_game_stats_wl.up.sql
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
python main.py price --season 2025-26
```

### 5. Start the Go API

```bash
cd backend
go mod tidy
go run cmd/api/main.go
```

### 6. Start the WebSocket server

```bash
cd backend
go run cmd/ws/main.go
```

### 7. Start the frontend

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
| WS | /ws | No | Real-time price/index stream |

## Engine CLI

```bash
python main.py sync-all --season 2025-26     # Full data sync
python main.py ingest --season 2025-26 --date 2025-12-01  # Single date
python main.py price --season 2025-26         # Run pricing
python main.py rebalance --season 2025-26     # Rebalance indexes
python main.py schedule --season 2025-26      # Daily scheduler (8am ET)
```
