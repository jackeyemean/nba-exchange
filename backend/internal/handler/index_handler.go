package handler

import (
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
	"github.com/jacky/hoop-exchange/backend/internal/repository"
)

type IndexHandler struct {
	Indexes *repository.IndexRepository
}

func NewIndexHandler(indexes *repository.IndexRepository) *IndexHandler {
	return &IndexHandler{Indexes: indexes}
}

func (h *IndexHandler) ListIndexes(c *gin.Context) {
	indexes, err := h.Indexes.ListAllWithPrices(c.Request.Context())
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to fetch indexes"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"indexes": indexes})
}

func (h *IndexHandler) GetIndex(c *gin.Context) {
	id, err := strconv.Atoi(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid index id"})
		return
	}

	rangeParam := c.DefaultQuery("range", "season")
	limit := 80
	offset := 0
	switch rangeParam {
	case "all":
		limit = 365
	case "season":
		limit = 80
	case "month":
		limit = 22
	case "week":
		limit = 5
	case "day":
		limit = 2  // today and yesterday for Past Day chart
		offset = 0
	}

	index, err := h.Indexes.GetByID(c.Request.Context(), id)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "index not found"})
		return
	}

	constituents, err := h.Indexes.GetConstituentsWithDetails(c.Request.Context(), id)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to fetch constituents"})
		return
	}

	history, err := h.Indexes.GetHistory(c.Request.Context(), id, limit, offset)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to fetch index history"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"index":        index,
		"constituents": constituents,
		"history":      history,
	})
}
