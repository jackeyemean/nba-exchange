-- ============================================================
-- Player Stock Exchange: Initial Schema
-- ============================================================

-- Seasons
CREATE TABLE seasons (
    id          SERIAL PRIMARY KEY,
    label       VARCHAR(10) NOT NULL UNIQUE,  -- e.g. '2025-26'
    start_date  DATE NOT NULL,
    end_date    DATE NOT NULL,
    is_active   BOOLEAN NOT NULL DEFAULT FALSE
);

-- Teams
CREATE TABLE teams (
    id              SERIAL PRIMARY KEY,
    external_id     VARCHAR(20) NOT NULL UNIQUE,  -- nba_api team id
    name            VARCHAR(100) NOT NULL,
    abbreviation    VARCHAR(10) NOT NULL,
    city            VARCHAR(100) NOT NULL
);

-- Team standings snapshot (refreshed daily)
CREATE TABLE team_standings (
    id          SERIAL PRIMARY KEY,
    team_id     INT NOT NULL REFERENCES teams(id),
    season_id   INT NOT NULL REFERENCES seasons(id),
    wins        INT NOT NULL DEFAULT 0,
    losses      INT NOT NULL DEFAULT 0,
    win_pct     NUMERIC(5,3) NOT NULL DEFAULT 0.000,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (team_id, season_id)
);

-- Players
CREATE TABLE players (
    id              SERIAL PRIMARY KEY,
    external_id     VARCHAR(20) NOT NULL UNIQUE,  -- nba_api player id
    first_name      VARCHAR(100) NOT NULL,
    last_name       VARCHAR(100) NOT NULL,
    birthdate       DATE,
    position        VARCHAR(20),
    height          VARCHAR(10),
    weight          INT
);

-- Player-season listing (one stock per player per season)
CREATE TYPE player_tier AS ENUM ('superstar', 'starter', 'rotation', 'bench');
CREATE TYPE listing_status AS ENUM ('ipo', 'active', 'injured_out', 'delisting', 'delisted');

CREATE TABLE player_seasons (
    id              SERIAL PRIMARY KEY,
    player_id       INT NOT NULL REFERENCES players(id),
    season_id       INT NOT NULL REFERENCES seasons(id),
    team_id         INT NOT NULL REFERENCES teams(id),
    tier            player_tier NOT NULL DEFAULT 'bench',
    float_shares    BIGINT NOT NULL DEFAULT 1000000,
    status          listing_status NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (player_id, season_id)
);

-- Player salaries (refreshed monthly)
CREATE TABLE player_salaries (
    id              SERIAL PRIMARY KEY,
    player_id       INT NOT NULL REFERENCES players(id),
    season_id       INT NOT NULL REFERENCES seasons(id),
    salary          BIGINT NOT NULL,  -- in USD cents
    percentile      NUMERIC(5,2),     -- computed across league
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (player_id, season_id)
);

-- Raw game stats (per player per game)
CREATE TABLE game_stats (
    id                  SERIAL PRIMARY KEY,
    player_season_id    INT NOT NULL REFERENCES player_seasons(id),
    game_date           DATE NOT NULL,
    external_game_id    VARCHAR(20) NOT NULL,
    minutes             NUMERIC(5,1) NOT NULL DEFAULT 0,
    pts                 INT NOT NULL DEFAULT 0,
    ast                 INT NOT NULL DEFAULT 0,
    reb                 INT NOT NULL DEFAULT 0,
    stl                 INT NOT NULL DEFAULT 0,
    blk                 INT NOT NULL DEFAULT 0,
    tov                 INT NOT NULL DEFAULT 0,
    fgm                 INT NOT NULL DEFAULT 0,
    fga                 INT NOT NULL DEFAULT 0,
    ftm                 INT NOT NULL DEFAULT 0,
    fta                 INT NOT NULL DEFAULT 0,
    raw_perf_score      NUMERIC(10,2),
    ts_pct              NUMERIC(5,3),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (player_season_id, external_game_id)
);

-- Price history (one row per player-season per trading day)
CREATE TABLE price_history (
    id                  SERIAL PRIMARY KEY,
    player_season_id    INT NOT NULL REFERENCES player_seasons(id),
    trade_date          DATE NOT NULL,
    perf_score          NUMERIC(10,4) NOT NULL,
    age_mult            NUMERIC(5,2) NOT NULL,
    win_pct_mult        NUMERIC(5,2) NOT NULL,
    salary_eff_mult     NUMERIC(5,2) NOT NULL,
    raw_score           NUMERIC(12,4) NOT NULL,
    price               NUMERIC(12,2) NOT NULL,
    market_cap          NUMERIC(18,2) NOT NULL,
    prev_price          NUMERIC(12,2),
    change_pct          NUMERIC(8,4),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (player_season_id, trade_date)
);

-- Users
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) NOT NULL UNIQUE,
    username        VARCHAR(50) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Wallets (virtual currency)
CREATE TABLE wallets (
    id          SERIAL PRIMARY KEY,
    user_id     UUID NOT NULL UNIQUE REFERENCES users(id),
    balance     NUMERIC(18,2) NOT NULL DEFAULT 100000.00,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Orders
CREATE TYPE order_side AS ENUM ('buy', 'sell');
CREATE TYPE order_status AS ENUM ('pending', 'filled', 'rejected', 'cancelled');

CREATE TABLE orders (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id),
    player_season_id    INT NOT NULL REFERENCES player_seasons(id),
    side                order_side NOT NULL,
    quantity            INT NOT NULL,
    price               NUMERIC(12,2) NOT NULL,
    total               NUMERIC(18,2) NOT NULL,
    status              order_status NOT NULL DEFAULT 'pending',
    filled_at           TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Trades (immutable ledger)
CREATE TABLE trades (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id        UUID NOT NULL REFERENCES orders(id),
    user_id         UUID NOT NULL REFERENCES users(id),
    player_season_id INT NOT NULL REFERENCES player_seasons(id),
    side            order_side NOT NULL,
    quantity        INT NOT NULL,
    price           NUMERIC(12,2) NOT NULL,
    total           NUMERIC(18,2) NOT NULL,
    executed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Positions (current holdings)
CREATE TABLE positions (
    id                  SERIAL PRIMARY KEY,
    user_id             UUID NOT NULL REFERENCES users(id),
    player_season_id    INT NOT NULL REFERENCES player_seasons(id),
    quantity            INT NOT NULL DEFAULT 0,
    avg_cost            NUMERIC(12,2) NOT NULL DEFAULT 0,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, player_season_id)
);

-- Indexes
CREATE TYPE index_type AS ENUM ('league', 'team', 'position', 'momentum');

CREATE TABLE indexes (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL UNIQUE,
    index_type      index_type NOT NULL,
    description     TEXT,
    team_id         INT REFERENCES teams(id),  -- only for team indexes
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index constituents (refreshed at daily rebalance)
CREATE TABLE index_constituents (
    id              SERIAL PRIMARY KEY,
    index_id        INT NOT NULL REFERENCES indexes(id),
    player_season_id INT NOT NULL REFERENCES player_seasons(id),
    weight          NUMERIC(8,6) NOT NULL,  -- e.g. 0.120000 = 12%
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (index_id, player_season_id)
);

-- Index price history
CREATE TABLE index_history (
    id          SERIAL PRIMARY KEY,
    index_id    INT NOT NULL REFERENCES indexes(id),
    trade_date  DATE NOT NULL,
    level       NUMERIC(12,4) NOT NULL,
    prev_level  NUMERIC(12,4),
    change_pct  NUMERIC(8,4),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (index_id, trade_date)
);

-- Leaderboard snapshots
CREATE TABLE leaderboard_snapshots (
    id              SERIAL PRIMARY KEY,
    user_id         UUID NOT NULL REFERENCES users(id),
    snapshot_date   DATE NOT NULL,
    portfolio_value NUMERIC(18,2) NOT NULL,
    cash_balance    NUMERIC(18,2) NOT NULL,
    total_value     NUMERIC(18,2) NOT NULL,
    rank            INT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, snapshot_date)
);

-- Performance indexes
CREATE INDEX idx_game_stats_player_season ON game_stats(player_season_id);
CREATE INDEX idx_game_stats_game_date ON game_stats(game_date);
CREATE INDEX idx_price_history_trade_date ON price_history(trade_date);
CREATE INDEX idx_price_history_player_season ON price_history(player_season_id);
CREATE INDEX idx_orders_user ON orders(user_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_trades_user ON trades(user_id);
CREATE INDEX idx_trades_executed ON trades(executed_at);
CREATE INDEX idx_positions_user ON positions(user_id);
CREATE INDEX idx_leaderboard_date_rank ON leaderboard_snapshots(snapshot_date, rank);
