package repository

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type IndexPosition struct {
	ID        int       `json:"id"`
	UserID    uuid.UUID `json:"userId"`
	IndexID   int       `json:"indexId"`
	Quantity  int       `json:"quantity"`
	AvgCost   float64   `json:"avgCost"`
	UpdatedAt time.Time `json:"updatedAt"`
}

type IndexPositionRepository struct {
	Pool *pgxpool.Pool
}

func NewIndexPositionRepository(pool *pgxpool.Pool) *IndexPositionRepository {
	return &IndexPositionRepository{Pool: pool}
}

func (r *IndexPositionRepository) GetByUserID(ctx context.Context, userID uuid.UUID) ([]IndexPosition, error) {
	rows, err := r.Pool.Query(ctx,
		`SELECT id, user_id, index_id, quantity, avg_cost, updated_at
		 FROM index_positions WHERE user_id = $1 AND quantity > 0
		 ORDER BY updated_at DESC`,
		userID,
	)
	if err != nil {
		return nil, fmt.Errorf("get index positions: %w", err)
	}
	defer rows.Close()

	var results []IndexPosition
	for rows.Next() {
		var p IndexPosition
		err := rows.Scan(&p.ID, &p.UserID, &p.IndexID, &p.Quantity, &p.AvgCost, &p.UpdatedAt)
		if err != nil {
			return nil, fmt.Errorf("scan index position: %w", err)
		}
		results = append(results, p)
	}
	return results, rows.Err()
}

func (r *IndexPositionRepository) GetByUserAndIndex(ctx context.Context, userID uuid.UUID, indexID int) (*IndexPosition, error) {
	p := &IndexPosition{}
	err := r.Pool.QueryRow(ctx,
		`SELECT id, user_id, index_id, quantity, avg_cost, updated_at
		 FROM index_positions WHERE user_id = $1 AND index_id = $2`,
		userID, indexID,
	).Scan(&p.ID, &p.UserID, &p.IndexID, &p.Quantity, &p.AvgCost, &p.UpdatedAt)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, nil
		}
		return nil, fmt.Errorf("get index position: %w", err)
	}
	return p, nil
}
