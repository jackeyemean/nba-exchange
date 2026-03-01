package handler

import (
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
	"github.com/jacky/nba-exchange/backend/internal/repository"
)

type IndexHandler struct {
	Indexes *repository.IndexRepository
}

func NewIndexHandler(indexes *repository.IndexRepository) *IndexHandler {
	return &IndexHandler{Indexes: indexes}
}

func (h *IndexHandler) ListIndexes(c *gin.Context) {
	indexes, err := h.Indexes.ListAll(c.Request.Context())
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

	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "30"))
	if limit <= 0 || limit > 365 {
		limit = 30
	}

	constituents, err := h.Indexes.GetConstituents(c.Request.Context(), id)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to fetch constituents"})
		return
	}

	history, err := h.Indexes.GetHistory(c.Request.Context(), id, limit)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to fetch index history"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"constituents": constituents,
		"history":      history,
	})
}
