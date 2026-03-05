package middleware

import (
	"context"
	"net/http"
	"strings"
	"sync"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
	"github.com/google/uuid"
	"github.com/jacky/hoop-exchange/backend/internal/repository"
	"github.com/MicahParks/keyfunc/v3"
)

// Supabase JWT claims (subset we care about)
type supabaseClaims struct {
	Sub      string         `json:"sub"`
	Email    string         `json:"email"`
	Metadata map[string]any `json:"user_metadata"`
	jwt.RegisteredClaims
}

var jwksCache struct {
	k   keyfunc.Keyfunc
	err error
	mu  sync.Mutex
}

// AuthRequired validates Supabase JWT and ensures user+wallet exist in our DB.
// Supports both HS256 (legacy secret) and RS256 (JWKS from Supabase URL).
func AuthRequired(
	supabaseJWTSecret string,
	supabaseURL string,
	userRepo *repository.UserRepository,
	walletRepo *repository.WalletRepository,
	startingBalance float64,
) gin.HandlerFunc {
	return func(c *gin.Context) {
		if supabaseJWTSecret == "" && supabaseURL == "" {
			c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": "auth not configured"})
			return
		}

		header := c.GetHeader("Authorization")
		if header == "" {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "missing authorization header"})
			return
		}

		parts := strings.SplitN(header, " ", 2)
		if len(parts) != 2 || parts[0] != "Bearer" {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "invalid authorization format"})
			return
		}

		userID, err := parseSupabaseToken(parts[1], supabaseJWTSecret, supabaseURL)
		if err != nil {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "invalid or expired token"})
			return
		}

		// Ensure user and wallet exist (first-time OAuth sign-in)
		if err := ensureUserAndWallet(c.Request.Context(), userRepo, walletRepo, userID, parts[1], supabaseJWTSecret, supabaseURL, startingBalance); err != nil {
			c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": "failed to sync user"})
			return
		}

		c.Set("user_id", userID)
		c.Next()
	}
}

func parseSupabaseToken(tokenStr, secret, supabaseURL string) (uuid.UUID, error) {
	// Try HS256 first (legacy)
	if secret != "" {
		if uid, err := parseWithHS256(tokenStr, secret); err == nil {
			return uid, nil
		}
	}

	// Try RS256/ES256 via JWKS (newer Supabase projects)
	if supabaseURL != "" {
		if uid, err := parseWithJWKS(tokenStr, strings.TrimSuffix(supabaseURL, "/")+"/auth/v1/.well-known/jwks.json"); err == nil {
			return uid, nil
		}
	}

	return uuid.Nil, jwt.ErrSignatureInvalid
}

func parseWithHS256(tokenStr, secret string) (uuid.UUID, error) {
	token, err := jwt.ParseWithClaims(tokenStr, &supabaseClaims{}, func(t *jwt.Token) (any, error) {
		if _, ok := t.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, jwt.ErrSignatureInvalid
		}
		return []byte(secret), nil
	})
	if err != nil {
		return uuid.Nil, err
	}

	claims, ok := token.Claims.(*supabaseClaims)
	if !ok || !token.Valid || claims.Sub == "" {
		return uuid.Nil, jwt.ErrSignatureInvalid
	}

	return uuid.Parse(claims.Sub)
}

func parseWithJWKS(tokenStr, jwksURL string) (uuid.UUID, error) {
	jwks, err := getJWKS(jwksURL)
	if err != nil {
		return uuid.Nil, err
	}

	token, err := jwt.ParseWithClaims(tokenStr, &supabaseClaims{}, jwks.Keyfunc)
	if err != nil {
		return uuid.Nil, err
	}

	claims, ok := token.Claims.(*supabaseClaims)
	if !ok || !token.Valid || claims.Sub == "" {
		return uuid.Nil, jwt.ErrSignatureInvalid
	}

	return uuid.Parse(claims.Sub)
}

func getJWKS(jwksURL string) (keyfunc.Keyfunc, error) {
	jwksCache.mu.Lock()
	defer jwksCache.mu.Unlock()

	if jwksCache.k != nil {
		return jwksCache.k, nil
	}
	if jwksCache.err != nil {
		return nil, jwksCache.err
	}

	k, err := keyfunc.NewDefaultCtx(context.Background(), []string{jwksURL})
	if err != nil {
		jwksCache.err = err
		return nil, err
	}
	jwksCache.k = k
	return k, nil
}

// parseSupabaseTokenForSync extracts user id, email, and username from token for creating new user.
func parseSupabaseTokenForSync(tokenStr, secret, supabaseURL string) (userID uuid.UUID, email, username string, err error) {
	userID, err = parseSupabaseToken(tokenStr, secret, supabaseURL)
	if err != nil {
		return uuid.Nil, "", "", err
	}

	// Parse without verification to get claims (we already verified above)
	parser := jwt.NewParser()
	var claims supabaseClaims
	_, _, err = parser.ParseUnverified(tokenStr, &claims)
	if err != nil {
		return uuid.Nil, "", "", err
	}

	email = claims.Email
	if email == "" {
		email = claims.Sub + "@oauth.local"
	}

	username = truncate(email, 50)
	if username == "" {
		username = "user_" + userID.String()[:8]
	}

	return userID, email, username, nil
}

func truncate(s string, max int) string {
	s = strings.TrimSpace(s)
	if len(s) <= max {
		return s
	}
	return s[:max]
}

func ensureUserAndWallet(ctx context.Context, userRepo *repository.UserRepository, walletRepo *repository.WalletRepository, userID uuid.UUID, tokenStr, secret, supabaseURL string, startingBalance float64) error {
	// Check if user already exists
	_, err := userRepo.GetByID(ctx, userID)
	if err == nil {
		// User exists: ensure wallet exists (in case it was never created)
		return walletRepo.CreateIfNotExists(ctx, userID, startingBalance)
	}

	_, email, _, err := parseSupabaseTokenForSync(tokenStr, secret, supabaseURL)
	if err != nil {
		return err
	}

	if err := userRepo.CreateOAuth(ctx, userID, email); err != nil {
		return err
	}
	if err := walletRepo.CreateIfNotExists(ctx, userID, startingBalance); err != nil {
		return err
	}
	return nil
}
