package service

import (
	"context"
	"fmt"

	"github.com/google/uuid"

	"github.com/jacky/hoop-exchange/backend/internal/repository"
)

type PortfolioPosition struct {
	PlayerSeasonID   int      `json:"playerSeasonId"`
	Quantity         int      `json:"quantity"`
	AvgCost          float64  `json:"avgCost"`
	CurrentPrice     float64  `json:"currentPrice"`
	MarketValue      float64  `json:"marketValue"`
	UnrealizedPnL    float64  `json:"unrealizedPnl"`
	UnrealizedPnLPct float64  `json:"unrealizedPnlPct"`
	Player           *struct {
		FirstName string `json:"firstName"`
		LastName  string `json:"lastName"`
	} `json:"player"`
}

type PortfolioIndexPosition struct {
	IndexID          int     `json:"indexId"`
	Quantity         int     `json:"quantity"`
	AvgCost          float64 `json:"avgCost"`
	CurrentPrice     float64 `json:"currentPrice"`
	MarketValue      float64 `json:"marketValue"`
	UnrealizedPnL    float64 `json:"unrealizedPnl"`
	UnrealizedPnLPct float64 `json:"unrealizedPnlPct"`
	Index            *struct {
		Name   string `json:"name"`
		Ticker string `json:"ticker"`
	} `json:"index"`
}

type PortfolioSummary struct {
	Positions          []PortfolioPosition      `json:"positions"`
	IndexPositions     []PortfolioIndexPosition `json:"indexPositions"`
	CashBalance        float64                  `json:"cashBalance"`
	TotalPositionValue float64                  `json:"totalPositionValue"`
	TotalValue         float64                  `json:"totalValue"`
}

type PortfolioService struct {
	Positions      *repository.PositionRepository
	IndexPositions *repository.IndexPositionRepository
	Players        *repository.PlayerRepository
	Indexes        *repository.IndexRepository
	Wallets        *repository.WalletRepository
}

func NewPortfolioService(
	positions *repository.PositionRepository,
	indexPositions *repository.IndexPositionRepository,
	players *repository.PlayerRepository,
	indexes *repository.IndexRepository,
	wallets *repository.WalletRepository,
) *PortfolioService {
	return &PortfolioService{
		Positions:      positions,
		IndexPositions: indexPositions,
		Players:        players,
		Indexes:        indexes,
		Wallets:        wallets,
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

	var portfolioPositions []PortfolioPosition
	var portfolioValue float64

	for _, pos := range positions {
		ph, err := s.Players.GetLatestPrice(ctx, pos.PlayerSeasonID)
		if err != nil {
			continue
		}

		marketValue := ph.Price * float64(pos.Quantity)
		pnl := (ph.Price - pos.AvgCost) * float64(pos.Quantity)
		var pnlPct float64
		if pos.AvgCost > 0 {
			pnlPct = (ph.Price - pos.AvgCost) / pos.AvgCost
		}

		playerSeason, err := s.Players.GetPlayerSeasonByID(ctx, pos.PlayerSeasonID)
		if err != nil {
			continue
		}

		portfolioPositions = append(portfolioPositions, PortfolioPosition{
			PlayerSeasonID:   pos.PlayerSeasonID,
			Quantity:         pos.Quantity,
			AvgCost:          pos.AvgCost,
			CurrentPrice:     ph.Price,
			MarketValue:      marketValue,
			UnrealizedPnL:    pnl,
			UnrealizedPnLPct: pnlPct,
			Player: &struct {
				FirstName string `json:"firstName"`
				LastName  string `json:"lastName"`
			}{
				FirstName: playerSeason.Player.FirstName,
				LastName:  playerSeason.Player.LastName,
			},
		})
		portfolioValue += marketValue
	}

	// Index positions
	indexPositions, err := s.IndexPositions.GetByUserID(ctx, userID)
	if err != nil {
		return nil, fmt.Errorf("get index positions: %w", err)
	}

	var portfolioIndexPositions []PortfolioIndexPosition
	for _, pos := range indexPositions {
		level, err := s.Indexes.GetLatestLevel(ctx, pos.IndexID)
		if err != nil {
			continue
		}
		marketValue := level * float64(pos.Quantity)
		pnl := (level - pos.AvgCost) * float64(pos.Quantity)
		var pnlPct float64
		if pos.AvgCost > 0 {
			pnlPct = (level - pos.AvgCost) / pos.AvgCost
		}

		idx, err := s.Indexes.GetByID(ctx, pos.IndexID)
		if err != nil {
			continue
		}
		ticker := ""
		if idx.Ticker != nil {
			ticker = *idx.Ticker
		}
		displayName := idx.Name
		if len(displayName) >= 6 && displayName[len(displayName)-6:] == " Index" {
			displayName = displayName[:len(displayName)-6]
		}

		portfolioIndexPositions = append(portfolioIndexPositions, PortfolioIndexPosition{
			IndexID:          pos.IndexID,
			Quantity:         pos.Quantity,
			AvgCost:          pos.AvgCost,
			CurrentPrice:     level,
			MarketValue:      marketValue,
			UnrealizedPnL:    pnl,
			UnrealizedPnLPct: pnlPct,
			Index: &struct {
				Name   string `json:"name"`
				Ticker string `json:"ticker"`
			}{
				Name:   displayName,
				Ticker: ticker,
			},
		})
		portfolioValue += marketValue
	}

	return &PortfolioSummary{
		Positions:          portfolioPositions,
		IndexPositions:     portfolioIndexPositions,
		CashBalance:        wallet.Balance,
		TotalPositionValue: portfolioValue,
		TotalValue:         wallet.Balance + portfolioValue,
	}, nil
}
