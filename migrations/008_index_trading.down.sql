ALTER TABLE trades DROP CONSTRAINT IF EXISTS trades_asset_check;
ALTER TABLE trades ALTER COLUMN player_season_id SET NOT NULL;
ALTER TABLE trades DROP COLUMN IF EXISTS index_id;

ALTER TABLE orders DROP CONSTRAINT IF EXISTS orders_asset_check;
ALTER TABLE orders ALTER COLUMN player_season_id SET NOT NULL;
ALTER TABLE orders DROP COLUMN IF EXISTS index_id;

DROP TABLE IF EXISTS index_positions;
