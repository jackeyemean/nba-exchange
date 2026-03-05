-- Index positions (user holdings in indexes)
CREATE TABLE index_positions (
    id          SERIAL PRIMARY KEY,
    user_id     UUID NOT NULL REFERENCES users(id),
    index_id    INT NOT NULL REFERENCES indexes(id),
    quantity    INT NOT NULL DEFAULT 0,
    avg_cost    NUMERIC(12,2) NOT NULL DEFAULT 0,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, index_id)
);

CREATE INDEX idx_index_positions_user ON index_positions(user_id);

-- Extend orders for index trades (player_season_id OR index_id, exactly one)
ALTER TABLE orders ADD COLUMN index_id INT REFERENCES indexes(id);
ALTER TABLE orders ALTER COLUMN player_season_id DROP NOT NULL;
ALTER TABLE orders ADD CONSTRAINT orders_asset_check
    CHECK (
        (player_season_id IS NOT NULL AND index_id IS NULL) OR
        (player_season_id IS NULL AND index_id IS NOT NULL)
    );

-- Extend trades for index trades
ALTER TABLE trades ADD COLUMN index_id INT REFERENCES indexes(id);
ALTER TABLE trades ALTER COLUMN player_season_id DROP NOT NULL;
ALTER TABLE trades ADD CONSTRAINT trades_asset_check
    CHECK (
        (player_season_id IS NOT NULL AND index_id IS NULL) OR
        (player_season_id IS NULL AND index_id IS NOT NULL)
    );
