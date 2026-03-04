package config

import (
	"os"
	"strconv"

	"github.com/joho/godotenv"
)

type Config struct {
	DatabaseURL string
	APIPort     string
	WSPort      string
	JWTSecret   string

	MarketOpenHour    int
	MarketOpenMinute  int
	MarketCloseHour   int
	MarketCloseMinute int
	MarketTimezone    string

	StartingBalance float64
	ScalingFactor   float64
}

func Load() (*Config, error) {
	_ = godotenv.Load("../.env")

	cfg := &Config{
		DatabaseURL: envOrDefault("DATABASE_URL", "postgres://nbaexchange:nbaexchange@localhost:5432/nbaexchange?sslmode=disable"),
		APIPort:     envOrDefault("API_PORT", "8080"),
		WSPort:         envOrDefault("WS_PORT", "8081"),
		JWTSecret:      envOrDefault("JWT_SECRET", "change-me-in-production"),
		MarketTimezone: envOrDefault("MARKET_TIMEZONE", "America/New_York"),
	}

	var err error
	cfg.MarketOpenHour, err = envIntOrDefault("MARKET_OPEN_HOUR", 6)
	if err != nil {
		return nil, err
	}
	cfg.MarketOpenMinute, err = envIntOrDefault("MARKET_OPEN_MINUTE", 0)
	if err != nil {
		return nil, err
	}
	cfg.MarketCloseHour, err = envIntOrDefault("MARKET_CLOSE_HOUR", 18)
	if err != nil {
		return nil, err
	}
	cfg.MarketCloseMinute, err = envIntOrDefault("MARKET_CLOSE_MINUTE", 0)
	if err != nil {
		return nil, err
	}
	cfg.StartingBalance, err = envFloatOrDefault("STARTING_BALANCE", 100000.00)
	if err != nil {
		return nil, err
	}
	cfg.ScalingFactor, err = envFloatOrDefault("SCALING_FACTOR", 2.08)
	if err != nil {
		return nil, err
	}

	return cfg, nil
}

func envOrDefault(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func envIntOrDefault(key string, fallback int) (int, error) {
	v := os.Getenv(key)
	if v == "" {
		return fallback, nil
	}
	return strconv.Atoi(v)
}

func envFloatOrDefault(key string, fallback float64) (float64, error) {
	v := os.Getenv(key)
	if v == "" {
		return fallback, nil
	}
	return strconv.ParseFloat(v, 64)
}
