package handler

import (
	"net/http"

	"github.com/TwiN/go-away"
	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/jacky/hoop-exchange/backend/internal/repository"
)

type AuthHandler struct {
	Users *repository.UserRepository
}

func NewAuthHandler(users *repository.UserRepository) *AuthHandler {
	return &AuthHandler{Users: users}
}

type meResponse struct {
	ID       string `json:"id"`
	Email    string `json:"email"`
	Username string `json:"username"`
}

type updateUsernameRequest struct {
	Username string `json:"username" binding:"required"`
}

// Me returns the current user (requires valid Supabase JWT via AuthRequired).
func (h *AuthHandler) Me(c *gin.Context) {
	userID, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "not authenticated"})
		return
	}

	uid, ok := userID.(uuid.UUID)
	if !ok {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "invalid user id"})
		return
	}

	user, err := h.Users.GetByID(c.Request.Context(), uid)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "user not found"})
		return
	}

	c.JSON(http.StatusOK, meResponse{
		ID:       user.ID.String(),
		Email:    user.Email,
		Username: user.Username,
	})
}

// UpdateUsername updates the current user's display name (shown on leaderboard).
func (h *AuthHandler) UpdateUsername(c *gin.Context) {
	userID, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "not authenticated"})
		return
	}

	uid, ok := userID.(uuid.UUID)
	if !ok {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "invalid user id"})
		return
	}

	var req updateUsernameRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "username is required"})
		return
	}

	username := req.Username
	if len(username) < 1 || len(username) > 23 {
		c.JSON(http.StatusBadRequest, gin.H{"error": "username must be 1-23 characters"})
		return
	}
	if goaway.IsProfane(username) {
		c.JSON(http.StatusBadRequest, gin.H{"error": "please choose a different username"})
		return
	}

	if err := h.Users.UpdateUsername(c.Request.Context(), uid, username); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"username": username})
}
