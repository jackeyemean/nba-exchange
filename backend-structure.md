# Backend Structure

The backend is a **Go** REST API server that serves the NBA Exchange frontend. It reads from PostgreSQL, handles authentication, trading, portfolio, leaderboard, and index data.

---

## Directory Layout

```
backend/
├── cmd/
│   └── api/main.go          # REST API entry point
├── internal/
│   ├── config/config.go     # Environment config (DB, JWT, market hours)
│   ├── db/
│   │   └── db.go            # PostgreSQL connection pool
│   ├── model/models.go      # Domain models (Player, Order, Trade, etc.)
│   ├── handler/             # HTTP request handlers
│   ├── service/             # Business logic
│   ├── repository/          # Data access layer
│   └── middleware/          # Auth, rate limit, market hours, abuse guard
├── go.mod, go.sum
└── Dockerfile
```

---

## API Routes

| Method | Path | Auth | Handler | Description |
|--------|------|------|---------|-------------|
| POST | `/api/auth/register` | No | AuthHandler.Register | Create account |
| POST | `/api/auth/login` | No | AuthHandler.Login | Login |
| GET | `/api/players` | No | PlayerHandler.ListActive | List active players with prices |
| GET | `/api/players/:id` | No | PlayerHandler.GetDetail | Player detail + price history |
| POST | `/api/orders` | Yes | TradingHandler.PlaceOrder | Place buy/sell order |
| GET | `/api/portfolio` | Yes | PortfolioHandler.GetPortfolio | User portfolio |
| GET | `/api/orders` | Yes | PortfolioHandler.ListOrders | Order history |
| GET | `/api/trades` | Yes | PortfolioHandler.ListTrades | Trade history |
| GET | `/api/indexes` | No | IndexHandler.ListIndexes | List indexes |
| GET | `/api/indexes/:id` | No | IndexHandler.GetIndex | Index detail + constituents |
| GET | `/api/leaderboard` | No | LeaderboardHandler.GetLeaderboard | Rankings |

---

## Models (`internal/model/models.go`)

### Core Entities
- **Season** – Season label (e.g. 2025-26), start/end dates
- **Team** – NBA team (external_id, name, abbreviation, city)
- **TeamStanding** – Wins, losses, win_pct per team per season
- **Player** – Player identity (external_id, first_name, last_name, birthdate, position)
- **PlayerSeason** – One stock per player per season (tier, float_shares, status)
- **GameStat** – Per-game stats (pts, ast, reb, stl, blk, tov, fgm, fga, etc.)
- **PriceHistory** – Per-player-season per-trade-date (price, market_cap, change_pct)

### Listing & Tiers
- **ListingStatus** – `ipo`, `active`, `injured_out`, `delisting`, `delisted`
- **PlayerTier** – `magnificent_7`, `blue_chip`, `growth`, `mid_cap`, `small_cap`, `penny_stock`

### Trading
- **User** – Email, username, password hash
- **Wallet** – User balance
- **Order** – Buy/sell order (side, quantity, price, status)
- **Trade** – Executed trade record
- **Position** – User holdings (quantity, avg_cost)

### Indexes
- **Index** – Index definition (name, type, ticker, team_id)
- **IndexConstituent** – Player weights in index
- **IndexHistory** – Index level per trade date
- **LeaderboardSnapshot** – User rankings by total value

---

## Services

| Service | Purpose |
|---------|---------|
| **AuthService** | Register, login, JWT generation |
| **TradingService** | Place order, update wallet, create position/trade |
| **PortfolioService** | Compute portfolio value, positions, P&L |

---

## Repositories

| Repository | Tables / Queries |
|------------|------------------|
| UserRepository | users |
| WalletRepository | wallets |
| PlayerRepository | players, player_seasons, price_history |
| OrderRepository | orders |
| TradeRepository | trades |
| PositionRepository | positions |
| IndexRepository | indexes, index_constituents, index_history |
| LeaderboardRepository | leaderboard_snapshots |

---

## Middleware

| Middleware | Purpose |
|------------|---------|
| **RateLimiter** | 100 req/min global |
| **AbuseGuard** | 30 orders/min per user, max 500k per order |
| **AuthRequired** | JWT validation for protected routes |
| **MarketOpen** | 6:00 AM–6:00 PM ET (configurable) |

---

## Data Flow

1. **Engine** writes prices/indexes to PostgreSQL (daily at market open)
2. **API** reads from PostgreSQL for REST responses
3. **Frontend** fetches data via REST; data refreshes on page load or navigation

---

## Configuration (Environment)

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `JWT_SECRET` | Secret for JWT signing |
| `API_PORT` | REST API port (default 8080) |
| `STARTING_BALANCE` | New user starting balance |
| `MARKET_TIMEZONE` | Market timezone (e.g. America/New_York) |
| `MARKET_OPEN_HOUR`, `MARKET_OPEN_MINUTE` | Market open time |
| `MARKET_CLOSE_HOUR`, `MARKET_CLOSE_MINUTE` | Market close time |

---

## Suggested Modularization

For future scaling and readability:

1. **`internal/api/`** – Route definitions grouped by domain (auth, players, trading, indexes)
2. **`internal/domain/`** – Domain logic separated from handlers
3. **`internal/repository/`** – Keep as-is; consider interfaces for testing
4. **`internal/middleware/`** – Keep; add logging, request ID middleware
