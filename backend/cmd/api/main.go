package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"

	"github.com/jacky/hoop-exchange/backend/internal/cache"
	"github.com/jacky/hoop-exchange/backend/internal/config"
	"github.com/jacky/hoop-exchange/backend/internal/db"
	"github.com/jacky/hoop-exchange/backend/internal/handler"
	"github.com/jacky/hoop-exchange/backend/internal/middleware"
	"github.com/jacky/hoop-exchange/backend/internal/repository"
	"github.com/jacky/hoop-exchange/backend/internal/service"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		log.Fatal("load config: ", err)
	}
	if cfg.SupabaseJWTSecret == "" && cfg.SupabaseURL == "" {
		log.Fatal("SUPABASE_JWT_SECRET or SUPABASE_URL is required for auth")
	}

	ctx := context.Background()

	pool, err := db.NewPool(ctx, cfg.DatabaseURL)
	if err != nil {
		log.Fatal("connect db: ", err)
	}
	defer pool.Close()

	userRepo := repository.NewUserRepository(pool)
	walletRepo := repository.NewWalletRepository(pool)
	playerRepo := repository.NewPlayerRepository(pool)
	orderRepo := repository.NewOrderRepository(pool)
	tradeRepo := repository.NewTradeRepository(pool)
	positionRepo := repository.NewPositionRepository(pool)
	indexPositionRepo := repository.NewIndexPositionRepository(pool)
	indexRepo := repository.NewIndexRepository(pool)
	leaderboardRepo := repository.NewLeaderboardRepository(pool)

	tradingSvc := service.NewTradingService(pool)
	portfolioSvc := service.NewPortfolioService(positionRepo, indexPositionRepo, playerRepo, indexRepo, walletRepo)

	authH := handler.NewAuthHandler(userRepo)
	playersCache := cache.NewTTL(30 * time.Second)
	playerH := handler.NewPlayerHandler(playerRepo, playersCache)
	tradingH := handler.NewTradingHandler(tradingSvc)
	portfolioH := handler.NewPortfolioHandler(portfolioSvc, orderRepo, tradeRepo)
	indexH := handler.NewIndexHandler(indexRepo)
	leaderboardH := handler.NewLeaderboardHandler(leaderboardRepo)

	r := gin.Default()

	r.Use(func(c *gin.Context) {
		c.Header("Access-Control-Allow-Origin", "*")
		c.Header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
		c.Header("Access-Control-Allow-Headers", "Content-Type, Authorization")
		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(204)
			return
		}
		c.Next()
	})

	rateLimiter := middleware.NewRateLimiter(100, time.Minute)
	r.Use(rateLimiter.Middleware())

	abuseGuard := middleware.NewAbuseGuard(30, 500_000)

	api := r.Group("/api")
	{
		api.GET("/players", playerH.ListActive)
		api.GET("/players/:id", playerH.GetDetail)

		api.GET("/indexes", indexH.ListIndexes)
		api.GET("/indexes/:id", indexH.GetIndex)

		api.GET("/leaderboard", leaderboardH.GetLeaderboard)

		protected := api.Group("")
		protected.Use(middleware.AuthRequired(cfg.SupabaseJWTSecret, cfg.SupabaseURL, userRepo, walletRepo, cfg.StartingBalance))
		{
			protected.GET("/auth/me", authH.Me)
			protected.PATCH("/auth/me", authH.UpdateUsername)
			protected.POST("/orders",
				abuseGuard.Middleware(),
				middleware.MarketOpen(
					cfg.MarketTimezone,
					cfg.MarketOpenHour, cfg.MarketOpenMinute,
					cfg.MarketCloseHour, cfg.MarketCloseMinute,
				),
				tradingH.PlaceOrder,
			)

			protected.GET("/portfolio", portfolioH.GetPortfolio)
			protected.GET("/orders", portfolioH.ListOrders)
			protected.GET("/trades", portfolioH.ListTrades)
		}
	}

	srv := &http.Server{
		Addr:    ":" + cfg.APIPort,
		Handler: r,
	}

	go func() {
		log.Printf("API server starting on :%s", cfg.APIPort)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatal("server error: ", err)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("shutting down...")
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := srv.Shutdown(shutdownCtx); err != nil {
		log.Fatal("server shutdown: ", err)
	}
}
