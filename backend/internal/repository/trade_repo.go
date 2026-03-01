package repository

import (
	"context"
	"fmt"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/jacky/nba-exchange/backend/internal/model"
)

type TradeRepository struct {
	Pool *pgxpool.Pool
}

func NewTradeRepository(pool *pgxpool.Pool) *TradeRepository {
	return &TradeRepository{Pool: pool}
}

func (r *TradeRepository) Create(ctx context.Context, trade *model.Trade) error {
	_, err := r.Pool.Exec(ctx,
		`INSERT INTO trades (id, order_id, user_id, player_season_id, side, quantity, price, total)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`,
		trade.ID, trade.OrderID, trade.UserID, trade.PlayerSeasonID,
		trade.Side, trade.Quantity, trade.Price, trade.Total,
	)
	if err != nil {
		return fmt.Errorf("create trade: %w", err)
	}
	return nil
}

func (r *TradeRepository) ListByUserID(ctx context.Context, userID uuid.UUID, limit int) ([]model.Trade, error) {
	rows, err := r.Pool.Query(ctx,
		`SELECT id, order_id, user_id, player_season_id, side, quantity, price, total, executed_at
		 FROM trades WHERE user_id = $1
		 ORDER BY executed_at DESC
		 LIMIT $2`,
		userID, limit,
	)
	if err != nil {
		return nil, fmt.Errorf("list trades: %w", err)
	}
	defer rows.Close()

	var results []model.Trade
	for rows.Next() {
		var t model.Trade
		err := rows.Scan(&t.ID, &t.OrderID, &t.UserID, &t.PlayerSeasonID,
			&t.Side, &t.Quantity, &t.Price, &t.Total, &t.ExecutedAt)
		if err != nil {
			return nil, fmt.Errorf("scan trade: %w", err)
		}
		results = append(results, t)
	}
	return results, rows.Err()
}
