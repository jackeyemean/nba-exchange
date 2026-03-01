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

func (r *IndexRepository) ListAll(ctx context.Context) ([]model.Index, error) {
	rows, err := r.Pool.Query(ctx,
		`SELECT id, name, index_type, description, team_id, created_at
		 FROM indexes ORDER BY name`,
	)
	if err != nil {
		return nil, fmt.Errorf("list indexes: %w", err)
	}
	defer rows.Close()

	var results []model.Index
	for rows.Next() {
		var idx model.Index
		err := rows.Scan(&idx.ID, &idx.Name, &idx.IndexType, &idx.Description, &idx.TeamID, &idx.CreatedAt)
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
