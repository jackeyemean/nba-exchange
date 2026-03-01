package repository

import (
	"context"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/jacky/nba-exchange/backend/internal/model"
)

type LeaderboardRepository struct {
	Pool *pgxpool.Pool
}

func NewLeaderboardRepository(pool *pgxpool.Pool) *LeaderboardRepository {
	return &LeaderboardRepository{Pool: pool}
}

func (r *LeaderboardRepository) GetByDate(ctx context.Context, date time.Time, limit int) ([]model.LeaderboardSnapshot, error) {
	rows, err := r.Pool.Query(ctx,
		`SELECT ls.id, ls.user_id, ls.snapshot_date, ls.portfolio_value, ls.cash_balance,
		        ls.total_value, ls.rank, ls.created_at, u.username
		 FROM leaderboard_snapshots ls
		 JOIN users u ON u.id = ls.user_id
		 WHERE ls.snapshot_date = $1
		 ORDER BY ls.rank ASC NULLS LAST
		 LIMIT $2`,
		date, limit,
	)
	if err != nil {
		return nil, fmt.Errorf("get leaderboard: %w", err)
	}
	defer rows.Close()

	var results []model.LeaderboardSnapshot
	for rows.Next() {
		var s model.LeaderboardSnapshot
		err := rows.Scan(&s.ID, &s.UserID, &s.SnapshotDate, &s.PortfolioValue,
			&s.CashBalance, &s.TotalValue, &s.Rank, &s.CreatedAt, &s.Username)
		if err != nil {
			return nil, fmt.Errorf("scan leaderboard: %w", err)
		}
		results = append(results, s)
	}
	return results, rows.Err()
}
