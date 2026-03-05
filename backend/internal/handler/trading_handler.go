package handler

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/jacky/hoop-exchange/backend/internal/model"
	"github.com/jacky/hoop-exchange/backend/internal/service"
)

type TradingHandler struct {
	Trading *service.TradingService
}

func NewTradingHandler(trading *service.TradingService) *TradingHandler {
	return &TradingHandler{Trading: trading}
}

type placeOrderRequest struct {
	PlayerSeasonID int    `json:"player_season_id"`
	IndexID        int    `json:"index_id"`
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

	hasPlayer := req.PlayerSeasonID != 0
	hasIndex := req.IndexID != 0
	if hasPlayer == hasIndex {
		c.JSON(http.StatusBadRequest, gin.H{"error": "provide exactly one of player_season_id or index_id"})
		return
	}

	var trade *model.Trade
	var err error
	if hasPlayer {
		trade, err = h.Trading.PlaceOrder(
			c.Request.Context(),
			userID.(uuid.UUID),
			req.PlayerSeasonID,
			model.OrderSide(req.Side),
			req.Quantity,
		)
	} else {
		trade, err = h.Trading.PlaceIndexOrder(
			c.Request.Context(),
			userID.(uuid.UUID),
			req.IndexID,
			model.OrderSide(req.Side),
			req.Quantity,
		)
	}
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, gin.H{"trade": trade})
}
