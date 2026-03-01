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

	"github.com/jacky/nba-exchange/backend/internal/config"
	"github.com/jacky/nba-exchange/backend/internal/db"
	"github.com/jacky/nba-exchange/backend/internal/ws"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		log.Fatal("load config: ", err)
	}

	rdb, err := db.NewRedis(cfg.RedisURL)
	if err != nil {
		log.Fatal("connect redis: ", err)
	}
	defer rdb.Close()

	hub := ws.NewHub()
	go hub.Run()

	ctx := context.Background()
	hub.SubscribeRedis(ctx, rdb, "prices", "indexes")

	r := gin.Default()
	r.GET("/ws", hub.HandleWebSocket)

	srv := &http.Server{
		Addr:    ":" + cfg.WSPort,
		Handler: r,
	}

	go func() {
		log.Printf("WebSocket server starting on :%s", cfg.WSPort)
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
