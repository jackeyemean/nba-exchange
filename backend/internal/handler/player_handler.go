package handler

import (
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
	"github.com/jacky/nba-exchange/backend/internal/repository"
)

type PlayerHandler struct {
	Players *repository.PlayerRepository
}

func NewPlayerHandler(players *repository.PlayerRepository) *PlayerHandler {
	return &PlayerHandler{Players: players}
}

func (h *PlayerHandler) ListActive(c *gin.Context) {
	seasonID, err := strconv.Atoi(c.DefaultQuery("season_id", "1"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid season_id"})
		return
	}

	players, err := h.Players.ListActiveWithPrices(c.Request.Context(), seasonID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to fetch players"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"players": players})
}

func (h *PlayerHandler) GetDetail(c *gin.Context) {
	id, err := strconv.Atoi(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid player id"})
		return
	}

	playerSeason, err := h.Players.GetPlayerSeasonByID(c.Request.Context(), id)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "player not found"})
		return
	}

	history, err := h.Players.GetPriceHistory(c.Request.Context(), id, 365)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to fetch price history"})
		return
	}

	teamAbbr := ""
	if playerSeason.Team != nil {
		teamAbbr = playerSeason.Team.Abbreviation
	}

	position := ""
	if playerSeason.Player.Position != nil {
		position = *playerSeason.Player.Position
	}

	playerInfo := gin.H{
		"id":               playerSeason.ID,
		"firstName":        playerSeason.Player.FirstName,
		"lastName":         playerSeason.Player.LastName,
		"position":         position,
		"teamAbbreviation": teamAbbr,
		"tier":             playerSeason.Tier,
		"floatShares":      playerSeason.FloatShares,
		"status":           playerSeason.Status,
	}

	c.JSON(http.StatusOK, gin.H{
		"player": playerInfo,
		"prices": history,
	})
}
