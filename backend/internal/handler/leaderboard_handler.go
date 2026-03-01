package handler

import (
	"net/http"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/jacky/nba-exchange/backend/internal/repository"
)

type LeaderboardHandler struct {
	Leaderboard *repository.LeaderboardRepository
}

func NewLeaderboardHandler(leaderboard *repository.LeaderboardRepository) *LeaderboardHandler {
	return &LeaderboardHandler{Leaderboard: leaderboard}
}

func (h *LeaderboardHandler) GetLeaderboard(c *gin.Context) {
	dateStr := c.DefaultQuery("date", time.Now().Format("2006-01-02"))
	date, err := time.Parse("2006-01-02", dateStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid date format, use YYYY-MM-DD"})
		return
	}

	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "50"))
	if limit <= 0 || limit > 200 {
		limit = 50
	}

	snapshots, err := h.Leaderboard.GetByDate(c.Request.Context(), date, limit)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to fetch leaderboard"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"leaderboard": snapshots})
}
