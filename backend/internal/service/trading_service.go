package service

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jacky/nba-exchange/backend/internal/model"
)

type TradingService struct {
	Pool *pgxpool.Pool
}

func NewTradingService(pool *pgxpool.Pool) *TradingService {
	return &TradingService{Pool: pool}
}

func (s *TradingService) PlaceOrder(ctx context.Context, userID uuid.UUID, playerSeasonID int, side model.OrderSide, quantity int) (*model.Trade, error) {
	if quantity <= 0 {
		return nil, errors.New("quantity must be positive")
	}

	tx, err := s.Pool.BeginTx(ctx, pgx.TxOptions{})
	if err != nil {
		return nil, fmt.Errorf("begin tx: %w", err)
	}
	defer tx.Rollback(ctx)

	var price float64
	err = tx.QueryRow(ctx,
		`SELECT price FROM price_history
		 WHERE player_season_id = $1
		 ORDER BY trade_date DESC LIMIT 1`,
		playerSeasonID,
	).Scan(&price)
	if err != nil {
		return nil, fmt.Errorf("get current price: %w", err)
	}

	total := price * float64(quantity)
	now := time.Now()
	orderID := uuid.New()
	tradeID := uuid.New()

	switch side {
	case model.SideBuy:
		var balance float64
		err = tx.QueryRow(ctx,
			`SELECT balance FROM wallets WHERE user_id = $1 FOR UPDATE`,
			userID,
		).Scan(&balance)
		if err != nil {
			return nil, fmt.Errorf("get wallet: %w", err)
		}
		if balance < total {
			return nil, errors.New("insufficient balance")
		}

		_, err = tx.Exec(ctx,
			`UPDATE wallets SET balance = balance - $1, updated_at = NOW() WHERE user_id = $2`,
			total, userID,
		)
		if err != nil {
			return nil, fmt.Errorf("deduct balance: %w", err)
		}

		// Compute new average cost
		var existingQty int
		var existingAvg float64
		err = tx.QueryRow(ctx,
			`SELECT COALESCE(quantity, 0), COALESCE(avg_cost, 0)
			 FROM positions WHERE user_id = $1 AND player_season_id = $2`,
			userID, playerSeasonID,
		).Scan(&existingQty, &existingAvg)
		if err != nil && !errors.Is(err, pgx.ErrNoRows) {
			return nil, fmt.Errorf("get existing position: %w", err)
		}

		newQty := existingQty + quantity
		newAvgCost := price
		if newQty > 0 {
			newAvgCost = (existingAvg*float64(existingQty) + price*float64(quantity)) / float64(newQty)
		}

		_, err = tx.Exec(ctx,
			`INSERT INTO positions (user_id, player_season_id, quantity, avg_cost)
			 VALUES ($1, $2, $3, $4)
			 ON CONFLICT (user_id, player_season_id)
			 DO UPDATE SET quantity = $3, avg_cost = $4, updated_at = NOW()`,
			userID, playerSeasonID, newQty, newAvgCost,
		)
		if err != nil {
			return nil, fmt.Errorf("upsert position: %w", err)
		}

	case model.SideSell:
		var posQty int
		err = tx.QueryRow(ctx,
			`SELECT quantity FROM positions
			 WHERE user_id = $1 AND player_season_id = $2 FOR UPDATE`,
			userID, playerSeasonID,
		).Scan(&posQty)
		if err != nil {
			return nil, fmt.Errorf("get position: %w", err)
		}
		if posQty < quantity {
			return nil, errors.New("insufficient shares")
		}

		_, err = tx.Exec(ctx,
			`UPDATE wallets SET balance = balance + $1, updated_at = NOW() WHERE user_id = $2`,
			total, userID,
		)
		if err != nil {
			return nil, fmt.Errorf("add balance: %w", err)
		}

		_, err = tx.Exec(ctx,
			`UPDATE positions SET quantity = quantity - $1, updated_at = NOW()
			 WHERE user_id = $2 AND player_season_id = $3`,
			quantity, userID, playerSeasonID,
		)
		if err != nil {
			return nil, fmt.Errorf("reduce position: %w", err)
		}

	default:
		return nil, fmt.Errorf("invalid order side: %s", side)
	}

	_, err = tx.Exec(ctx,
		`INSERT INTO orders (id, user_id, player_season_id, side, quantity, price, total, status, filled_at)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)`,
		orderID, userID, playerSeasonID, side, quantity, price, total, model.OrderFilled, now,
	)
	if err != nil {
		return nil, fmt.Errorf("create order: %w", err)
	}

	_, err = tx.Exec(ctx,
		`INSERT INTO trades (id, order_id, user_id, player_season_id, side, quantity, price, total)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`,
		tradeID, orderID, userID, playerSeasonID, side, quantity, price, total,
	)
	if err != nil {
		return nil, fmt.Errorf("create trade: %w", err)
	}

	if err := tx.Commit(ctx); err != nil {
		return nil, fmt.Errorf("commit tx: %w", err)
	}

	return &model.Trade{
		ID:             tradeID,
		OrderID:        orderID,
		UserID:         userID,
		PlayerSeasonID: playerSeasonID,
		Side:           side,
		Quantity:       quantity,
		Price:          price,
		Total:          total,
		ExecutedAt:     now,
	}, nil
}
