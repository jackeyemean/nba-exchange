package middleware

import (
	"net/http"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
)

type orderWindow struct {
	timestamps []time.Time
	notional   float64
}

type AbuseGuard struct {
	mu              sync.Mutex
	userWindows     map[uuid.UUID]*orderWindow
	maxOrdersPerMin int
	maxNotionalPerMin float64
	window          time.Duration
}

func NewAbuseGuard(maxOrdersPerMin int, maxNotionalPerMin float64) *AbuseGuard {
	ag := &AbuseGuard{
		userWindows:       make(map[uuid.UUID]*orderWindow),
		maxOrdersPerMin:   maxOrdersPerMin,
		maxNotionalPerMin: maxNotionalPerMin,
		window:            time.Minute,
	}
	go ag.cleanup()
	return ag
}

func (ag *AbuseGuard) cleanup() {
	for {
		time.Sleep(5 * time.Minute)
		ag.mu.Lock()
		cutoff := time.Now().Add(-ag.window)
		for uid, w := range ag.userWindows {
			pruned := make([]time.Time, 0, len(w.timestamps))
			for _, t := range w.timestamps {
				if t.After(cutoff) {
					pruned = append(pruned, t)
				}
			}
			if len(pruned) == 0 {
				delete(ag.userWindows, uid)
			} else {
				w.timestamps = pruned
			}
		}
		ag.mu.Unlock()
	}
}

func (ag *AbuseGuard) Middleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		raw, exists := c.Get("user_id")
		if !exists {
			c.Next()
			return
		}
		userID := raw.(uuid.UUID)
		now := time.Now()
		cutoff := now.Add(-ag.window)

		ag.mu.Lock()
		w, exists := ag.userWindows[userID]
		if !exists {
			w = &orderWindow{}
			ag.userWindows[userID] = w
		}

		pruned := make([]time.Time, 0, len(w.timestamps))
		for _, t := range w.timestamps {
			if t.After(cutoff) {
				pruned = append(pruned, t)
			}
		}
		w.timestamps = pruned

		if len(w.timestamps) >= ag.maxOrdersPerMin {
			ag.mu.Unlock()
			c.AbortWithStatusJSON(http.StatusTooManyRequests, gin.H{
				"error": "Too many orders. Please slow down.",
			})
			return
		}

		w.timestamps = append(w.timestamps, now)
		ag.mu.Unlock()
		c.Next()
	}
}
