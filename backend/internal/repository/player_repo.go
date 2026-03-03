package repository

import (
	"context"
	"fmt"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/jacky/nba-exchange/backend/internal/model"
)

// PriceHistoryRange: all (from 2023-24), season (current), month, week
const (
	RangeAll    = "all"
	RangeSeason = "season"
	RangeMonth  = "month"
	RangeWeek   = "week"
)

type PlayerWithPrice struct {
	ID               int      `json:"id"`
	FirstName        string   `json:"firstName"`
	LastName         string   `json:"lastName"`
	Position         string   `json:"position"`
	TeamAbbreviation string   `json:"teamAbbreviation"`
	Tier             string   `json:"tier"`
	FloatShares      int64    `json:"floatShares"`
	Status           string   `json:"status"`
	Price            *float64 `json:"price"`
	ChangePct        *float64 `json:"changePct"`
	MarketCap        *float64 `json:"marketCap"`
}

type PlayerRepository struct {
	Pool *pgxpool.Pool
}

func NewPlayerRepository(pool *pgxpool.Pool) *PlayerRepository {
	return &PlayerRepository{Pool: pool}
}

func (r *PlayerRepository) ListActiveBySeasonID(ctx context.Context, seasonID int) ([]model.PlayerSeason, error) {
	rows, err := r.Pool.Query(ctx,
		`SELECT ps.id, ps.player_id, ps.season_id, ps.team_id, ps.tier, ps.float_shares, ps.status, ps.created_at,
		        p.id, p.external_id, p.first_name, p.last_name, p.birthdate, p.position, p.height, p.weight
		 FROM player_seasons ps
		 JOIN players p ON p.id = ps.player_id
		 WHERE ps.season_id = $1 AND ps.status NOT IN ('delisted')
		 ORDER BY p.last_name, p.first_name`,
		seasonID,
	)
	if err != nil {
		return nil, fmt.Errorf("list active players: %w", err)
	}
	defer rows.Close()

	var results []model.PlayerSeason
	for rows.Next() {
		var ps model.PlayerSeason
		var p model.Player
		err := rows.Scan(
			&ps.ID, &ps.PlayerID, &ps.SeasonID, &ps.TeamID, &ps.Tier, &ps.FloatShares, &ps.Status, &ps.CreatedAt,
			&p.ID, &p.ExternalID, &p.FirstName, &p.LastName, &p.Birthdate, &p.Position, &p.Height, &p.Weight,
		)
		if err != nil {
			return nil, fmt.Errorf("scan player season: %w", err)
		}
		ps.Player = &p
		results = append(results, ps)
	}
	return results, rows.Err()
}

func (r *PlayerRepository) GetPlayerSeasonByID(ctx context.Context, id int) (*model.PlayerSeason, error) {
	ps := &model.PlayerSeason{Player: &model.Player{}, Team: &model.Team{}}
	err := r.Pool.QueryRow(ctx,
		`SELECT ps.id, ps.player_id, ps.season_id, ps.team_id, ps.tier, ps.float_shares, ps.status, ps.created_at,
		        p.id, p.external_id, COALESCE(p.ticker, ''), p.first_name, p.last_name, p.birthdate, p.position, p.height, p.weight,
		        t.id, t.external_id, t.name, t.abbreviation, t.city
		 FROM player_seasons ps
		 JOIN players p ON p.id = ps.player_id
		 JOIN teams t ON t.id = ps.team_id
		 WHERE ps.id = $1`,
		id,
	).Scan(
		&ps.ID, &ps.PlayerID, &ps.SeasonID, &ps.TeamID, &ps.Tier, &ps.FloatShares, &ps.Status, &ps.CreatedAt,
		&ps.Player.ID, &ps.Player.ExternalID, &ps.Player.FirstName, &ps.Player.LastName, &ps.Player.Birthdate, &ps.Player.Position, &ps.Player.Height, &ps.Player.Weight,
		&ps.Team.ID, &ps.Team.ExternalID, &ps.Team.Name, &ps.Team.Abbreviation, &ps.Team.City,
	)
	if err != nil {
		return nil, fmt.Errorf("get player season: %w", err)
	}
	return ps, nil
}

func (r *PlayerRepository) ListActiveWithPrices(ctx context.Context, seasonID int) ([]PlayerWithPrice, error) {
	rows, err := r.Pool.Query(ctx,
		`SELECT ps.id, p.first_name, p.last_name, COALESCE(p.position, ''), t.abbreviation,
		        ps.tier::text, ps.float_shares, ps.status::text,
		        ph.price,
		        CASE WHEN prev.price IS NOT NULL AND prev.price > 0
		             THEN ROUND((ph.price - prev.price) / prev.price, 4)
		             ELSE ph.change_pct
		        END AS change_pct,
		        ph.market_cap
		 FROM player_seasons ps
		 JOIN players p ON p.id = ps.player_id
		 JOIN teams t ON t.id = ps.team_id
		 LEFT JOIN LATERAL (
		     SELECT price, change_pct, market_cap
		     FROM price_history
		     WHERE player_season_id = ps.id
		     ORDER BY trade_date DESC
		     LIMIT 1
		 ) ph ON true
		 LEFT JOIN LATERAL (
		     SELECT price FROM price_history
		     WHERE player_season_id = ps.id
		       AND price IS DISTINCT FROM ph.price
		     ORDER BY trade_date DESC
		     LIMIT 1
		 ) prev ON true
		 WHERE ps.season_id = $1 AND ps.status NOT IN ('delisted')
		 ORDER BY ph.market_cap DESC NULLS LAST`,
		seasonID,
	)
	if err != nil {
		return nil, fmt.Errorf("list active with prices: %w", err)
	}
	defer rows.Close()

	var results []PlayerWithPrice
	for rows.Next() {
		var p PlayerWithPrice
		err := rows.Scan(
			&p.ID, &p.FirstName, &p.LastName, &p.Position, &p.TeamAbbreviation,
			&p.Tier, &p.FloatShares, &p.Status,
			&p.Price, &p.ChangePct, &p.MarketCap,
		)
		if err != nil {
			return nil, fmt.Errorf("scan player with price: %w", err)
		}
		results = append(results, p)
	}
	return results, rows.Err()
}

func (r *PlayerRepository) GetLatestPrice(ctx context.Context, playerSeasonID int) (*model.PriceHistory, error) {
	ph := &model.PriceHistory{}
	err := r.Pool.QueryRow(ctx,
		`WITH latest AS (
		     SELECT * FROM price_history
		     WHERE player_season_id = $1
		     ORDER BY trade_date DESC LIMIT 1
		 ),
		 prev_diff AS (
		     SELECT price FROM price_history
		     WHERE player_season_id = $1
		       AND price IS DISTINCT FROM (SELECT price FROM latest)
		     ORDER BY trade_date DESC LIMIT 1
		 )
		 SELECT l.id, l.player_season_id, l.trade_date, l.perf_score, l.age_mult, l.win_pct_mult,
		        l.salary_eff_mult, l.raw_score, l.price, l.market_cap, l.prev_price,
		        CASE WHEN pd.price IS NOT NULL AND pd.price > 0
		             THEN ROUND((l.price - pd.price) / pd.price, 4)
		             ELSE l.change_pct
		        END,
		        l.created_at
		 FROM latest l
		 LEFT JOIN LATERAL (SELECT price FROM prev_diff) pd ON true`,
		playerSeasonID,
	).Scan(&ph.ID, &ph.PlayerSeasonID, &ph.TradeDate, &ph.PerfScore, &ph.AgeMult, &ph.WinPctMult,
		&ph.SalaryEffMult, &ph.RawScore, &ph.Price, &ph.MarketCap, &ph.PrevPrice, &ph.ChangePct, &ph.CreatedAt)
	if err != nil {
		return nil, fmt.Errorf("get latest price: %w", err)
	}
	return ph, nil
}

func (r *PlayerRepository) GetPriceHistory(ctx context.Context, playerSeasonID int, limit int) ([]model.PriceHistory, error) {
	rows, err := r.Pool.Query(ctx,
		`SELECT id, player_season_id, trade_date, perf_score, age_mult, win_pct_mult,
		        salary_eff_mult, raw_score, price, market_cap, prev_price, change_pct, created_at
		 FROM price_history
		 WHERE player_season_id = $1
		 ORDER BY trade_date DESC
		 LIMIT $2`,
		playerSeasonID, limit,
	)
	if err != nil {
		return nil, fmt.Errorf("get price history: %w", err)
	}
	defer rows.Close()

	var results []model.PriceHistory
	for rows.Next() {
		var ph model.PriceHistory
		err := rows.Scan(&ph.ID, &ph.PlayerSeasonID, &ph.TradeDate, &ph.PerfScore, &ph.AgeMult, &ph.WinPctMult,
			&ph.SalaryEffMult, &ph.RawScore, &ph.Price, &ph.MarketCap, &ph.PrevPrice, &ph.ChangePct, &ph.CreatedAt)
		if err != nil {
			return nil, fmt.Errorf("scan price history: %w", err)
		}
		results = append(results, ph)
	}
	return results, rows.Err()
}

// GetActiveSeasonID returns the current season (most recent by start_date).
func (r *PlayerRepository) GetActiveSeasonID(ctx context.Context) (int, error) {
	var id int
	err := r.Pool.QueryRow(ctx,
		`SELECT id FROM seasons ORDER BY start_date DESC LIMIT 1`).Scan(&id)
	if err != nil {
		return 1, nil // fallback if no seasons
	}
	return id, nil
}

// GetPriceHistoryForPlayer returns price history across all seasons for a player,
// filtered by range: all (from 2023-24), season (current only), month, week.
// Results are ordered chronologically (oldest first) for chart display.
func (r *PlayerRepository) GetPriceHistoryForPlayer(ctx context.Context, playerID, playerSeasonID int, rangeFilter string) ([]model.PriceHistory, error) {
	var query string
	var args []interface{}

	switch rangeFilter {
	case RangeSeason:
		query = `SELECT ph.id, ph.player_season_id, ph.trade_date, ph.perf_score, ph.age_mult, ph.win_pct_mult,
		         ph.salary_eff_mult, ph.raw_score, ph.price, ph.market_cap, ph.prev_price, ph.change_pct, ph.created_at
		         FROM price_history ph
		         WHERE ph.player_season_id = $1
		         ORDER BY ph.trade_date ASC`
		args = []interface{}{playerSeasonID}
	case RangeMonth:
		query = `SELECT ph.id, ph.player_season_id, ph.trade_date, ph.perf_score, ph.age_mult, ph.win_pct_mult,
		         ph.salary_eff_mult, ph.raw_score, ph.price, ph.market_cap, ph.prev_price, ph.change_pct, ph.created_at
		         FROM price_history ph
		         JOIN player_seasons ps ON ph.player_season_id = ps.id
		         WHERE ps.player_id = $1 AND ph.trade_date >= CURRENT_DATE - INTERVAL '30 days'
		         ORDER BY ph.trade_date ASC`
		args = []interface{}{playerID}
	case RangeWeek:
		query = `SELECT ph.id, ph.player_season_id, ph.trade_date, ph.perf_score, ph.age_mult, ph.win_pct_mult,
		         ph.salary_eff_mult, ph.raw_score, ph.price, ph.market_cap, ph.prev_price, ph.change_pct, ph.created_at
		         FROM price_history ph
		         JOIN player_seasons ps ON ph.player_season_id = ps.id
		         WHERE ps.player_id = $1 AND ph.trade_date >= CURRENT_DATE - INTERVAL '7 days'
		         ORDER BY ph.trade_date ASC`
		args = []interface{}{playerID}
	default: // RangeAll - from start of 2023-24 simulation
		query = `SELECT ph.id, ph.player_season_id, ph.trade_date, ph.perf_score, ph.age_mult, ph.win_pct_mult,
		         ph.salary_eff_mult, ph.raw_score, ph.price, ph.market_cap, ph.prev_price, ph.change_pct, ph.created_at
		         FROM price_history ph
		         JOIN player_seasons ps ON ph.player_season_id = ps.id
		         WHERE ps.player_id = $1 AND ph.trade_date >= '2023-10-24'
		         ORDER BY ph.trade_date ASC`
		args = []interface{}{playerID}
	}

	rows, err := r.Pool.Query(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("get price history for player: %w", err)
	}
	defer rows.Close()

	var results []model.PriceHistory
	for rows.Next() {
		var ph model.PriceHistory
		err := rows.Scan(&ph.ID, &ph.PlayerSeasonID, &ph.TradeDate, &ph.PerfScore, &ph.AgeMult, &ph.WinPctMult,
			&ph.SalaryEffMult, &ph.RawScore, &ph.Price, &ph.MarketCap, &ph.PrevPrice, &ph.ChangePct, &ph.CreatedAt)
		if err != nil {
			return nil, fmt.Errorf("scan price history: %w", err)
		}
		results = append(results, ph)
	}
	return results, rows.Err()
}
