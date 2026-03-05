package repository

import (
	"context"
	"fmt"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/jacky/hoop-exchange/backend/internal/model"
)

type OrderRepository struct {
	Pool *pgxpool.Pool
}

func NewOrderRepository(pool *pgxpool.Pool) *OrderRepository {
	return &OrderRepository{Pool: pool}
}

func (r *OrderRepository) Create(ctx context.Context, order *model.Order) error {
	var psID, idxID interface{}
	if order.PlayerSeasonID != nil {
		psID = *order.PlayerSeasonID
	} else {
		psID = nil
	}
	if order.IndexID != nil {
		idxID = *order.IndexID
	} else {
		idxID = nil
	}
	_, err := r.Pool.Exec(ctx,
		`INSERT INTO orders (id, user_id, player_season_id, index_id, side, quantity, price, total, status, filled_at)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)`,
		order.ID, order.UserID, psID, idxID, order.Side,
		order.Quantity, order.Price, order.Total, order.Status, order.FilledAt,
	)
	if err != nil {
		return fmt.Errorf("create order: %w", err)
	}
	return nil
}

func (r *OrderRepository) GetByID(ctx context.Context, id uuid.UUID) (*model.Order, error) {
	order := &model.Order{}
	err := r.Pool.QueryRow(ctx,
		`SELECT id, user_id, player_season_id, index_id, side, quantity, price, total, status, filled_at, created_at
		 FROM orders WHERE id = $1`,
		id,
	).Scan(&order.ID, &order.UserID, &order.PlayerSeasonID, &order.IndexID, &order.Side,
		&order.Quantity, &order.Price, &order.Total, &order.Status, &order.FilledAt, &order.CreatedAt)
	if err != nil {
		return nil, fmt.Errorf("get order by id: %w", err)
	}
	return order, nil
}

func (r *OrderRepository) ListByUserID(ctx context.Context, userID uuid.UUID, limit int) ([]model.Order, error) {
	rows, err := r.Pool.Query(ctx,
		`SELECT id, user_id, player_season_id, index_id, side, quantity, price, total, status, filled_at, created_at
		 FROM orders WHERE user_id = $1
		 ORDER BY created_at DESC
		 LIMIT $2`,
		userID, limit,
	)
	if err != nil {
		return nil, fmt.Errorf("list orders: %w", err)
	}
	defer rows.Close()

	var results []model.Order
	for rows.Next() {
		var o model.Order
		err := rows.Scan(&o.ID, &o.UserID, &o.PlayerSeasonID, &o.IndexID, &o.Side,
			&o.Quantity, &o.Price, &o.Total, &o.Status, &o.FilledAt, &o.CreatedAt)
		if err != nil {
			return nil, fmt.Errorf("scan order: %w", err)
		}
		results = append(results, o)
	}
	return results, rows.Err()
}
