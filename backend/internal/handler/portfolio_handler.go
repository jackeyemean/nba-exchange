package handler

import (
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/jacky/nba-exchange/backend/internal/repository"
	"github.com/jacky/nba-exchange/backend/internal/service"
)

type PortfolioHandler struct {
	Portfolio *service.PortfolioService
	Orders    *repository.OrderRepository
	Trades    *repository.TradeRepository
}

func NewPortfolioHandler(portfolio *service.PortfolioService, orders *repository.OrderRepository, trades *repository.TradeRepository) *PortfolioHandler {
	return &PortfolioHandler{
		Portfolio: portfolio,
		Orders:    orders,
		Trades:    trades,
	}
}

func (h *PortfolioHandler) GetPortfolio(c *gin.Context) {
	userID := c.MustGet("user_id").(uuid.UUID)

	summary, err := h.Portfolio.GetPortfolio(c.Request.Context(), userID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to fetch portfolio"})
		return
	}

	c.JSON(http.StatusOK, summary)
}

func (h *PortfolioHandler) ListOrders(c *gin.Context) {
	userID := c.MustGet("user_id").(uuid.UUID)

	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "50"))
	if limit <= 0 || limit > 200 {
		limit = 50
	}

	orders, err := h.Orders.ListByUserID(c.Request.Context(), userID, limit)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to fetch orders"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"orders": orders})
}

func (h *PortfolioHandler) ListTrades(c *gin.Context) {
	userID := c.MustGet("user_id").(uuid.UUID)

	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "50"))
	if limit <= 0 || limit > 200 {
		limit = 50
	}

	trades, err := h.Trades.ListByUserID(c.Request.Context(), userID, limit)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to fetch trades"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"trades": trades})
}
