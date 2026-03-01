package service

import (
	"context"
	"fmt"

	"github.com/google/uuid"

	"github.com/jacky/nba-exchange/backend/internal/repository"
)

type PortfolioHolding struct {
	PlayerSeasonID int     `json:"player_season_id"`
	Quantity       int     `json:"quantity"`
	AvgCost        float64 `json:"avg_cost"`
	CurrentPrice   float64 `json:"current_price"`
	MarketValue    float64 `json:"market_value"`
	UnrealizedPnL  float64 `json:"unrealized_pnl"`
}

type PortfolioSummary struct {
	Holdings       []PortfolioHolding `json:"holdings"`
	CashBalance    float64            `json:"cash_balance"`
	PortfolioValue float64            `json:"portfolio_value"`
	TotalValue     float64            `json:"total_value"`
}

type PortfolioService struct {
	Positions *repository.PositionRepository
	Players   *repository.PlayerRepository
	Wallets   *repository.WalletRepository
}

func NewPortfolioService(positions *repository.PositionRepository, players *repository.PlayerRepository, wallets *repository.WalletRepository) *PortfolioService {
	return &PortfolioService{
		Positions: positions,
		Players:   players,
		Wallets:   wallets,
	}
}

func (s *PortfolioService) GetPortfolio(ctx context.Context, userID uuid.UUID) (*PortfolioSummary, error) {
	wallet, err := s.Wallets.GetByUserID(ctx, userID)
	if err != nil {
		return nil, fmt.Errorf("get wallet: %w", err)
	}

	positions, err := s.Positions.GetByUserID(ctx, userID)
	if err != nil {
		return nil, fmt.Errorf("get positions: %w", err)
	}

	var holdings []PortfolioHolding
	var portfolioValue float64

	for _, pos := range positions {
		ph, err := s.Players.GetLatestPrice(ctx, pos.PlayerSeasonID)
		if err != nil {
			continue
		}

		marketValue := ph.Price * float64(pos.Quantity)
		pnl := (ph.Price - pos.AvgCost) * float64(pos.Quantity)

		holdings = append(holdings, PortfolioHolding{
			PlayerSeasonID: pos.PlayerSeasonID,
			Quantity:       pos.Quantity,
			AvgCost:        pos.AvgCost,
			CurrentPrice:   ph.Price,
			MarketValue:    marketValue,
			UnrealizedPnL:  pnl,
		})
		portfolioValue += marketValue
	}

	return &PortfolioSummary{
		Holdings:       holdings,
		CashBalance:    wallet.Balance,
		PortfolioValue: portfolioValue,
		TotalValue:     wallet.Balance + portfolioValue,
	}, nil
}
