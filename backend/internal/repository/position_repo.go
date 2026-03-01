package repository

import (
	"context"
	"fmt"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/jacky/nba-exchange/backend/internal/model"
)

type PositionRepository struct {
	Pool *pgxpool.Pool
}

func NewPositionRepository(pool *pgxpool.Pool) *PositionRepository {
	return &PositionRepository{Pool: pool}
}

func (r *PositionRepository) Upsert(ctx context.Context, userID uuid.UUID, playerSeasonID int, quantityDelta int, newAvgCost float64) error {
	_, err := r.Pool.Exec(ctx,
		`INSERT INTO positions (user_id, player_season_id, quantity, avg_cost)
		 VALUES ($1, $2, $3, $4)
		 ON CONFLICT (user_id, player_season_id) DO UPDATE
		 SET quantity = positions.quantity + $3, avg_cost = $4, updated_at = NOW()`,
		userID, playerSeasonID, quantityDelta, newAvgCost,
	)
	if err != nil {
		return fmt.Errorf("upsert position: %w", err)
	}
	return nil
}

func (r *PositionRepository) GetByUserID(ctx context.Context, userID uuid.UUID) ([]model.Position, error) {
	rows, err := r.Pool.Query(ctx,
		`SELECT id, user_id, player_season_id, quantity, avg_cost, updated_at
		 FROM positions WHERE user_id = $1 AND quantity > 0
		 ORDER BY updated_at DESC`,
		userID,
	)
	if err != nil {
		return nil, fmt.Errorf("get positions: %w", err)
	}
	defer rows.Close()

	var results []model.Position
	for rows.Next() {
		var p model.Position
		err := rows.Scan(&p.ID, &p.UserID, &p.PlayerSeasonID, &p.Quantity, &p.AvgCost, &p.UpdatedAt)
		if err != nil {
			return nil, fmt.Errorf("scan position: %w", err)
		}
		results = append(results, p)
	}
	return results, rows.Err()
}

func (r *PositionRepository) GetByUserAndPlayer(ctx context.Context, userID uuid.UUID, playerSeasonID int) (*model.Position, error) {
	pos := &model.Position{}
	err := r.Pool.QueryRow(ctx,
		`SELECT id, user_id, player_season_id, quantity, avg_cost, updated_at
		 FROM positions WHERE user_id = $1 AND player_season_id = $2`,
		userID, playerSeasonID,
	).Scan(&pos.ID, &pos.UserID, &pos.PlayerSeasonID, &pos.Quantity, &pos.AvgCost, &pos.UpdatedAt)
	if err != nil {
		return nil, fmt.Errorf("get position: %w", err)
	}
	return pos, nil
}
