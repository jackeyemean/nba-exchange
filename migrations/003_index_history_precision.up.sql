-- Increase precision for index_history level/prev_level to prevent overflow
-- (NUMERIC(12,4) max ~99M; compounding returns can exceed this)
ALTER TABLE index_history
  ALTER COLUMN level TYPE NUMERIC(18,4),
  ALTER COLUMN prev_level TYPE NUMERIC(18,4);
