package repository

import (
	"context"
	"database/sql"
	"fmt"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/jacky/hoop-exchange/backend/internal/model"
)

type TradeRepository struct {
	Pool *pgxpool.Pool
}

func NewTradeRepository(pool *pgxpool.Pool) *TradeRepository {
	return &TradeRepository{Pool: pool}
}

func (r *TradeRepository) Create(ctx context.Context, trade *model.Trade) error {
	var psID, idxID interface{}
	if trade.PlayerSeasonID != nil {
		psID = *trade.PlayerSeasonID
	} else {
		psID = nil
	}
	if trade.IndexID != nil {
		idxID = *trade.IndexID
	} else {
		idxID = nil
	}
	_, err := r.Pool.Exec(ctx,
		`INSERT INTO trades (id, order_id, user_id, player_season_id, index_id, side, quantity, price, total)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)`,
		trade.ID, trade.OrderID, trade.UserID, psID, idxID,
		trade.Side, trade.Quantity, trade.Price, trade.Total,
	)
	if err != nil {
		return fmt.Errorf("create trade: %w", err)
	}
	return nil
}

func (r *TradeRepository) ListByUserID(ctx context.Context, userID uuid.UUID, limit int) ([]model.Trade, error) {
	rows, err := r.Pool.Query(ctx,
		`SELECT id, order_id, user_id, player_season_id, index_id, side, quantity, price, total, executed_at
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
		err := rows.Scan(&t.ID, &t.OrderID, &t.UserID, &t.PlayerSeasonID, &t.IndexID,
			&t.Side, &t.Quantity, &t.Price, &t.Total, &t.ExecutedAt)
		if err != nil {
			return nil, fmt.Errorf("scan trade: %w", err)
		}
		results = append(results, t)
	}
	return results, rows.Err()
}

type TradeWithPlayer struct {
	model.Trade
	Player *struct {
		FirstName string `json:"firstName"`
		LastName  string `json:"lastName"`
	} `json:"player"`
	Index *struct {
		Name string `json:"name"`
	} `json:"index,omitempty"`
}

func (r *TradeRepository) ListByUserIDWithPlayer(ctx context.Context, userID uuid.UUID, limit int) ([]TradeWithPlayer, error) {
	rows, err := r.Pool.Query(ctx,
		`SELECT t.id, t.order_id, t.user_id, t.player_season_id, t.index_id, t.side, t.quantity, t.price, t.total, t.executed_at,
		        p.first_name, p.last_name,
		        idx.name
		 FROM trades t
		 LEFT JOIN player_seasons ps ON ps.id = t.player_season_id
		 LEFT JOIN players p ON p.id = ps.player_id
		 LEFT JOIN indexes idx ON idx.id = t.index_id
		 WHERE t.user_id = $1
		 ORDER BY t.executed_at DESC
		 LIMIT $2`,
		userID, limit,
	)
	if err != nil {
		return nil, fmt.Errorf("list trades with player: %w", err)
	}
	defer rows.Close()

	var results []TradeWithPlayer
	for rows.Next() {
		var twp TradeWithPlayer
		var firstName, lastName, indexName sql.NullString
		err := rows.Scan(&twp.ID, &twp.OrderID, &twp.UserID, &twp.PlayerSeasonID, &twp.IndexID,
			&twp.Side, &twp.Quantity, &twp.Price, &twp.Total, &twp.ExecutedAt,
			&firstName, &lastName, &indexName)
		if err != nil {
			return nil, fmt.Errorf("scan trade: %w", err)
		}
		if firstName.Valid && lastName.Valid {
			twp.Player = &struct {
				FirstName string `json:"firstName"`
				LastName  string `json:"lastName"`
			}{FirstName: firstName.String, LastName: lastName.String}
		}
		if indexName.Valid && indexName.String != "" {
			twp.Index = &struct {
				Name string `json:"name"`
			}{Name: indexName.String}
		}
		results = append(results, twp)
	}
	return results, rows.Err()
}
