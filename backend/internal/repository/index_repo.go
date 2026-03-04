package repository

import (
	"context"
	"fmt"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/jacky/nba-exchange/backend/internal/model"
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
		`SELECT i.id, i.name, i.index_type, i.description, i.team_id, i.created_at,
		        t.abbreviation
		 FROM indexes i
		 LEFT JOIN teams t ON t.id = i.team_id
		 WHERE i.id = $1`,
		id,
	).Scan(&idx.ID, &idx.Name, &idx.IndexType, &idx.Description, &idx.TeamID, &idx.CreatedAt, &idx.TeamAbbreviation)
	if err != nil {
		return nil, fmt.Errorf("get index: %w", err)
	}
	return idx, nil
}

func (r *IndexRepository) ListAll(ctx context.Context) ([]model.Index, error) {
	rows, err := r.Pool.Query(ctx,
		`SELECT i.id, i.name, i.index_type, i.description, i.team_id, i.created_at,
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
		err := rows.Scan(&idx.ID, &idx.Name, &idx.IndexType, &idx.Description, &idx.TeamID, &idx.CreatedAt, &idx.TeamAbbreviation)
		if err != nil {
			return nil, fmt.Errorf("scan index: %w", err)
		}
		results = append(results, idx)
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
	rows, err := r.Pool.Query(ctx,
		`SELECT ic.id, ic.index_id, ic.player_season_id, ic.weight,
		        p.first_name, p.last_name,
		        COALESCE(p.position, ''),
		        COALESCE(t.abbreviation, ''),
		        ps.tier::text,
		        ps.float_shares,
		        COALESCE(ph.price, 0),
		        CASE WHEN prev.price IS NOT NULL AND prev.price > 0
		             THEN ROUND((ph.price - prev.price) / prev.price, 4)
		             ELSE ph.change_pct
		        END,
		        COALESCE(ph.market_cap, 0)
		 FROM index_constituents ic
		 JOIN player_seasons ps ON ps.id = ic.player_season_id
		 JOIN players p ON p.id = ps.player_id
		 LEFT JOIN teams t ON t.id = ps.team_id
		 LEFT JOIN LATERAL (
		     SELECT price, change_pct, market_cap
		     FROM price_history
		     WHERE player_season_id = ic.player_season_id
		     ORDER BY trade_date DESC LIMIT 1
		 ) ph ON true
		 LEFT JOIN LATERAL (
		     SELECT price FROM price_history
		     WHERE player_season_id = ic.player_season_id
		       AND price IS DISTINCT FROM ph.price
		     ORDER BY trade_date DESC LIMIT 1
		 ) prev ON true
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

func (r *IndexRepository) GetHistory(ctx context.Context, indexID int, limit int) ([]model.IndexHistory, error) {
	rows, err := r.Pool.Query(ctx,
		`SELECT id, index_id, trade_date, level, prev_level, change_pct, created_at
		 FROM index_history WHERE index_id = $1
		 ORDER BY trade_date DESC
		 LIMIT $2`,
		indexID, limit,
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
