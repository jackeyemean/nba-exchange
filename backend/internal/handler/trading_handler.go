package handler

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/jacky/nba-exchange/backend/internal/model"
	"github.com/jacky/nba-exchange/backend/internal/service"
)

type TradingHandler struct {
	Trading *service.TradingService
}

func NewTradingHandler(trading *service.TradingService) *TradingHandler {
	return &TradingHandler{Trading: trading}
}

type placeOrderRequest struct {
	PlayerSeasonID int    `json:"player_season_id" binding:"required"`
	Side           string `json:"side" binding:"required,oneof=buy sell"`
	Quantity       int    `json:"quantity" binding:"required,min=1"`
}

func (h *TradingHandler) PlaceOrder(c *gin.Context) {
	userID, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "unauthorized"})
		return
	}

	var req placeOrderRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	trade, err := h.Trading.PlaceOrder(
		c.Request.Context(),
		userID.(uuid.UUID),
		req.PlayerSeasonID,
		model.OrderSide(req.Side),
		req.Quantity,
	)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, gin.H{"trade": trade})
}
