package middleware

import (
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
)

func MarketOpen(timezone string, openHour, openMin, closeHour, closeMin int) gin.HandlerFunc {
	loc, err := time.LoadLocation(timezone)
	if err != nil {
		panic("invalid market timezone: " + err.Error())
	}

	return func(c *gin.Context) {
		now := time.Now().In(loc)

		weekday := now.Weekday()
		if weekday == time.Saturday || weekday == time.Sunday {
			c.AbortWithStatusJSON(http.StatusForbidden, gin.H{"error": "Market is closed"})
			return
		}

		open := time.Date(now.Year(), now.Month(), now.Day(), openHour, openMin, 0, 0, loc)
		close := time.Date(now.Year(), now.Month(), now.Day(), closeHour, closeMin, 0, 0, loc)

		if now.Before(open) || now.After(close) {
			c.AbortWithStatusJSON(http.StatusForbidden, gin.H{"error": "Market is closed"})
			return
		}

		c.Next()
	}
}
