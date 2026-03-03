-- Add WL (win/loss) to game_stats for computing team win% at any point in season
ALTER TABLE game_stats ADD COLUMN IF NOT EXISTS wl CHAR(1);
