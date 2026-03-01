package repository

import (
	"context"
	"fmt"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/jacky/nba-exchange/backend/internal/model"
)

type WalletRepository struct {
	Pool *pgxpool.Pool
}

func NewWalletRepository(pool *pgxpool.Pool) *WalletRepository {
	return &WalletRepository{Pool: pool}
}

func (r *WalletRepository) Create(ctx context.Context, userID uuid.UUID, initialBalance float64) (*model.Wallet, error) {
	wallet := &model.Wallet{}
	err := r.Pool.QueryRow(ctx,
		`INSERT INTO wallets (user_id, balance)
		 VALUES ($1, $2)
		 RETURNING id, user_id, balance, updated_at`,
		userID, initialBalance,
	).Scan(&wallet.ID, &wallet.UserID, &wallet.Balance, &wallet.UpdatedAt)
	if err != nil {
		return nil, fmt.Errorf("create wallet: %w", err)
	}
	return wallet, nil
}

func (r *WalletRepository) GetByUserID(ctx context.Context, userID uuid.UUID) (*model.Wallet, error) {
	wallet := &model.Wallet{}
	err := r.Pool.QueryRow(ctx,
		`SELECT id, user_id, balance, updated_at
		 FROM wallets WHERE user_id = $1`,
		userID,
	).Scan(&wallet.ID, &wallet.UserID, &wallet.Balance, &wallet.UpdatedAt)
	if err != nil {
		return nil, fmt.Errorf("get wallet by user id: %w", err)
	}
	return wallet, nil
}

func (r *WalletRepository) UpdateBalance(ctx context.Context, userID uuid.UUID, newBalance float64) error {
	_, err := r.Pool.Exec(ctx,
		`UPDATE wallets SET balance = $1, updated_at = NOW() WHERE user_id = $2`,
		newBalance, userID,
	)
	if err != nil {
		return fmt.Errorf("update wallet balance: %w", err)
	}
	return nil
}
