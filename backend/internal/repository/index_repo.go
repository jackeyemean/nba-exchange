package repository

import (
	"context"
	"fmt"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/jacky/hoop-exchange/backend/internal/model"
)

type IndexRepository struct {
	Pool *pgxpool.Pool
}

func NewIndexRepository(pool *pgxpool.Pool) *IndexRepository {
	return &IndexRepository{Pool: pool}
}

func (r *IndexRepository) GetByID(ctx context.Context, id int) (*model.Index, error) {
	idx := &model.Index{}
	err := r.Pool.QueryRow(ctx,
		`SELECT i.id, i.name, i.index_type, i.description, i.ticker, i.team_id, i.created_at,
		        t.abbreviation
		 FROM indexes i
		 LEFT JOIN teams t ON t.id = i.team_id
		 WHERE i.id = $1`,
		id,
	).Scan(&idx.ID, &idx.Name, &idx.IndexType, &idx.Description, &idx.Ticker, &idx.TeamID, &idx.CreatedAt, &idx.TeamAbbreviation)
	if err != nil {
		return nil, fmt.Errorf("get index: %w", err)
	}
	return idx, nil
}

// IndexWithPrices extends Index with latest level and daily change % (curr_day vs prev_day).
type IndexWithPrices struct {
	model.Index
	Level     *float64 `json:"level,omitempty"`
	ChangePct *float64 `json:"changePct,omitempty"`
}

func (r *IndexRepository) ListAll(ctx context.Context) ([]model.Index, error) {
	rows, err := r.Pool.Query(ctx,
		`SELECT i.id, i.name, i.index_type, i.description, i.ticker, i.team_id, i.created_at,
		        t.abbreviation
		 FROM indexes i
		 LEFT JOIN teams t ON t.id = i.team_id
		 ORDER BY i.name`,
	)
	if err != nil {
		return nil, fmt.Errorf("list indexes: %w", err)
	}
	defer rows.Close()

	var results []model.Index
	for rows.Next() {
		var idx model.Index
		err := rows.Scan(&idx.ID, &idx.Name, &idx.IndexType, &idx.Description, &idx.Ticker, &idx.TeamID, &idx.CreatedAt, &idx.TeamAbbreviation)
		if err != nil {
			return nil, fmt.Errorf("scan index: %w", err)
		}
		results = append(results, idx)
	}
	return results, rows.Err()
}

func (r *IndexRepository) ListAllWithPrices(ctx context.Context) ([]IndexWithPrices, error) {
	rows, err := r.Pool.Query(ctx,
		`SELECT i.id, i.name, i.index_type, i.description, i.ticker, i.team_id, i.created_at,
		        t.abbreviation,
		        curr.level,
		        CASE WHEN prev.level IS NOT NULL AND prev.level > 0
		             THEN ROUND((curr.level - prev.level) / prev.level, 6)
		             ELSE NULL
		        END AS change_pct
		 FROM indexes i
		 LEFT JOIN teams t ON t.id = i.team_id
		 LEFT JOIN LATERAL (
		     SELECT level FROM index_history
		     WHERE index_id = i.id
		     ORDER BY trade_date DESC
		     LIMIT 1
		 ) curr ON true
		 LEFT JOIN LATERAL (
		     SELECT level FROM index_history
		     WHERE index_id = i.id
		     ORDER BY trade_date DESC
		     OFFSET 1 LIMIT 1
		 ) prev ON true
		 ORDER BY i.name`,
	)
	if err != nil {
		return nil, fmt.Errorf("list indexes with prices: %w", err)
	}
	defer rows.Close()

	var results []IndexWithPrices
	for rows.Next() {
		var iw IndexWithPrices
		err := rows.Scan(&iw.ID, &iw.Name, &iw.IndexType, &iw.Description, &iw.Ticker, &iw.TeamID, &iw.CreatedAt, &iw.TeamAbbreviation,
			&iw.Level, &iw.ChangePct)
		if err != nil {
			return nil, fmt.Errorf("scan index with prices: %w", err)
		}
		results = append(results, iw)
	}
	return results, rows.Err()
}

func (r *IndexRepository) GetConstituents(ctx context.Context, indexID int) ([]model.IndexConstituent, error) {
	rows, err := r.Pool.Query(ctx,
		`SELECT id, index_id, player_season_id, weight, updated_at
		 FROM index_constituents WHERE index_id = $1
		 ORDER BY weight DESC`,
		indexID,
	)
	if err != nil {
		return nil, fmt.Errorf("get constituents: %w", err)
	}
	defer rows.Close()

	var results []model.IndexConstituent
	for rows.Next() {
		var ic model.IndexConstituent
		err := rows.Scan(&ic.ID, &ic.IndexID, &ic.PlayerSeasonID, &ic.Weight, &ic.UpdatedAt)
		if err != nil {
			return nil, fmt.Errorf("scan constituent: %w", err)
		}
		results = append(results, ic)
	}
	return results, rows.Err()
}

type ConstituentWithDetails struct {
	ID               int      `json:"id"`
	IndexID          int      `json:"indexId"`
	PlayerSeasonID   int      `json:"playerSeasonId"`
	Weight           float64  `json:"weight"`
	Player           *struct {
		FirstName string `json:"firstName"`
		LastName  string `json:"lastName"`
	} `json:"player"`
	Position         string   `json:"position"`
	TeamAbbreviation  string   `json:"teamAbbreviation"`
	Tier             string   `json:"tier"`
	FloatShares      int64    `json:"floatShares"`
	Price            float64  `json:"price"`
	ChangePct        *float64 `json:"changePct"`
	MarketCap        float64  `json:"marketCap"`
}

func (r *IndexRepository) GetConstituentsWithDetails(ctx context.Context, indexID int) ([]ConstituentWithDetails, error) {
	// Use stored change_pct from price_history (same trade_date as index) to avoid off-by-one.
	// Index rebalance uses price_history.change_pct for that trade_date; constituents must match.
	rows, err := r.Pool.Query(ctx,
		`SELECT ic.id, ic.index_id, ic.player_season_id, ic.weight,
		        p.first_name, p.last_name,
		        COALESCE(p.position, ''),
		        COALESCE(t.abbreviation, ''),
		        ps.tier::text,
		        ps.float_shares,
		        COALESCE(ph.price, 0),
		        ph.change_pct,
		        COALESCE(ph.market_cap, 0)
		 FROM index_constituents ic
		 JOIN player_seasons ps ON ps.id = ic.player_season_id
		 JOIN players p ON p.id = ps.player_id
		 LEFT JOIN teams t ON t.id = ps.team_id
		 LEFT JOIN LATERAL (
		     SELECT price, market_cap, change_pct
		     FROM price_history
		     WHERE player_season_id = ic.player_season_id
		     ORDER BY trade_date DESC LIMIT 1
		 ) ph ON true
		 WHERE ic.index_id = $1
		 ORDER BY ic.weight DESC`,
		indexID,
	)
	if err != nil {
		return nil, fmt.Errorf("get constituents with details: %w", err)
	}
	defer rows.Close()

	var results []ConstituentWithDetails
	for rows.Next() {
		var c ConstituentWithDetails
		var firstName, lastName string
		err := rows.Scan(&c.ID, &c.IndexID, &c.PlayerSeasonID, &c.Weight,
			&firstName, &lastName,
			&c.Position, &c.TeamAbbreviation, &c.Tier, &c.FloatShares,
			&c.Price, &c.ChangePct, &c.MarketCap)
		if err != nil {
			return nil, fmt.Errorf("scan constituent: %w", err)
		}
		c.Player = &struct {
			FirstName string `json:"firstName"`
			LastName  string `json:"lastName"`
		}{FirstName: firstName, LastName: lastName}
		results = append(results, c)
	}
	return results, rows.Err()
}

// GetLatestLevel returns the most recent index level (price) for trading.
func (r *IndexRepository) GetLatestLevel(ctx context.Context, indexID int) (float64, error) {
	var level float64
	err := r.Pool.QueryRow(ctx,
		`SELECT level FROM index_history
		 WHERE index_id = $1
		 ORDER BY trade_date DESC LIMIT 1`,
		indexID,
	).Scan(&level)
	if err != nil {
		return 0, fmt.Errorf("get latest level: %w", err)
	}
	return level, nil
}

func (r *IndexRepository) GetHistory(ctx context.Context, indexID int, limit int, offset int) ([]model.IndexHistory, error) {
	rows, err := r.Pool.Query(ctx,
		`SELECT id, index_id, trade_date, level, prev_level, change_pct, created_at
		 FROM index_history WHERE index_id = $1
		 ORDER BY trade_date DESC
		 OFFSET $2 LIMIT $3`,
		indexID, offset, limit,
	)
	if err != nil {
		return nil, fmt.Errorf("get index history: %w", err)
	}
	defer rows.Close()

	var results []model.IndexHistory
	for rows.Next() {
		var ih model.IndexHistory
		err := rows.Scan(&ih.ID, &ih.IndexID, &ih.TradeDate, &ih.Level, &ih.PrevLevel, &ih.ChangePct, &ih.CreatedAt)
		if err != nil {
			return nil, fmt.Errorf("scan index history: %w", err)
		}
		results = append(results, ih)
	}
	return results, rows.Err()
}
