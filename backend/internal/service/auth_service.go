package service

import (
	"context"
	"errors"
	"fmt"

	"golang.org/x/crypto/bcrypt"

	"github.com/jacky/nba-exchange/backend/internal/middleware"
	"github.com/jacky/nba-exchange/backend/internal/repository"
)

type AuthService struct {
	Users           *repository.UserRepository
	Wallets         *repository.WalletRepository
	JWTSecret       string
	StartingBalance float64
}

func NewAuthService(users *repository.UserRepository, wallets *repository.WalletRepository, jwtSecret string, startingBalance float64) *AuthService {
	return &AuthService{
		Users:           users,
		Wallets:         wallets,
		JWTSecret:       jwtSecret,
		StartingBalance: startingBalance,
	}
}

func (s *AuthService) Register(ctx context.Context, email, username, password string) (string, error) {
	if email == "" || username == "" || password == "" {
		return "", errors.New("email, username, and password are required")
	}

	hash, err := bcrypt.GenerateFromPassword([]byte(password), bcrypt.DefaultCost)
	if err != nil {
		return "", fmt.Errorf("hash password: %w", err)
	}

	user, err := s.Users.Create(ctx, email, username, string(hash))
	if err != nil {
		return "", fmt.Errorf("create user: %w", err)
	}

	_, err = s.Wallets.Create(ctx, user.ID, s.StartingBalance)
	if err != nil {
		return "", fmt.Errorf("create wallet: %w", err)
	}

	token, err := middleware.GenerateToken(user.ID, s.JWTSecret)
	if err != nil {
		return "", fmt.Errorf("generate token: %w", err)
	}

	return token, nil
}

func (s *AuthService) Login(ctx context.Context, email, password string) (string, error) {
	user, err := s.Users.GetByEmail(ctx, email)
	if err != nil {
		return "", errors.New("invalid email or password")
	}

	if err := bcrypt.CompareHashAndPassword([]byte(user.PasswordHash), []byte(password)); err != nil {
		return "", errors.New("invalid email or password")
	}

	token, err := middleware.GenerateToken(user.ID, s.JWTSecret)
	if err != nil {
		return "", fmt.Errorf("generate token: %w", err)
	}

	return token, nil
}
