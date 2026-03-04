package model

import (
	"time"

	"github.com/google/uuid"
)

type Season struct {
	ID        int       `json:"id"`
	Label     string    `json:"label"`
	StartDate time.Time `json:"startDate"`
	EndDate   time.Time `json:"endDate"`
	IsActive  bool      `json:"isActive"`
}

type Team struct {
	ID           int    `json:"id"`
	ExternalID   string `json:"externalId"`
	Name         string `json:"name"`
	Abbreviation string `json:"abbreviation"`
	City         string `json:"city"`
}

type TeamStanding struct {
	ID        int       `json:"id"`
	TeamID    int       `json:"teamId"`
	SeasonID  int       `json:"seasonId"`
	Wins      int       `json:"wins"`
	Losses    int       `json:"losses"`
	WinPct    float64   `json:"winPct"`
	UpdatedAt time.Time `json:"updatedAt"`
}

type Player struct {
	ID         int        `json:"id"`
	ExternalID string     `json:"externalId"`
	FirstName  string     `json:"firstName"`
	LastName   string     `json:"lastName"`
	Birthdate  *time.Time `json:"birthdate,omitempty"`
	Position   *string    `json:"position,omitempty"`
	Height     *string    `json:"height,omitempty"`
	Weight     *int       `json:"weight,omitempty"`
}

type PlayerTier string

const (
	TierMagnificent7 PlayerTier = "magnificent_7"
	TierBlueChip     PlayerTier = "blue_chip"
	TierGrowth       PlayerTier = "growth"
	TierMidCap       PlayerTier = "mid_cap"
	TierSmallCap     PlayerTier = "small_cap"
	TierPennyStock   PlayerTier = "penny_stock"
)

type ListingStatus string

const (
	StatusIPO      ListingStatus = "ipo"
	StatusActive   ListingStatus = "active"
	StatusInjured  ListingStatus = "injured_out"
	StatusDelisted ListingStatus = "delisted"
	StatusDelisting ListingStatus = "delisting"
)

type PlayerSeason struct {
	ID          int           `json:"id"`
	PlayerID    int           `json:"playerId"`
	SeasonID    int           `json:"seasonId"`
	TeamID      int           `json:"teamId"`
	Tier        PlayerTier    `json:"tier"`
	FloatShares int64         `json:"floatShares"`
	Status      ListingStatus `json:"status"`
	CreatedAt   time.Time     `json:"createdAt"`

	Player *Player `json:"player,omitempty"`
	Team   *Team   `json:"team,omitempty"`
}

type PlayerSalary struct {
	ID         int       `json:"id"`
	PlayerID   int       `json:"playerId"`
	SeasonID   int       `json:"seasonId"`
	Salary     int64     `json:"salary"`
	Percentile float64   `json:"percentile"`
	UpdatedAt  time.Time `json:"updatedAt"`
}

type GameStat struct {
	ID              int       `json:"id"`
	PlayerSeasonID  int       `json:"playerSeasonId"`
	GameDate        time.Time `json:"gameDate"`
	ExternalGameID  string    `json:"externalGameId"`
	Minutes         float64   `json:"minutes"`
	Pts             int       `json:"pts"`
	Ast             int       `json:"ast"`
	Reb             int       `json:"reb"`
	Stl             int       `json:"stl"`
	Blk             int       `json:"blk"`
	Tov             int       `json:"tov"`
	Fgm             int       `json:"fgm"`
	Fga             int       `json:"fga"`
	Ftm             int       `json:"ftm"`
	Fta             int       `json:"fta"`
	RawPerfScore    float64   `json:"rawPerfScore"`
	TsPct           float64   `json:"tsPct"`
	CreatedAt       time.Time `json:"createdAt"`
}

type PriceHistory struct {
	ID              int       `json:"id"`
	PlayerSeasonID  int       `json:"playerSeasonId"`
	TradeDate       time.Time `json:"tradeDate"`
	PerfScore       float64   `json:"perfScore"`
	AgeMult         float64   `json:"ageMult"`
	WinPctMult      float64   `json:"winPctMult"`
	SalaryEffMult   float64   `json:"injuryMult"` // DB column is salary_eff_mult; stores injury multiplier
	RawScore        float64   `json:"rawScore"`
	Price           float64   `json:"price"`
	MarketCap       float64   `json:"marketCap"`
	PrevPrice       *float64  `json:"prevPrice,omitempty"`
	ChangePct       *float64  `json:"changePct,omitempty"`
	CreatedAt       time.Time `json:"createdAt"`
}

type User struct {
	ID           uuid.UUID `json:"id"`
	Email        string    `json:"email"`
	Username     string    `json:"username"`
	PasswordHash string    `json:"-"`
	CreatedAt    time.Time `json:"createdAt"`
}

type Wallet struct {
	ID        int       `json:"id"`
	UserID    uuid.UUID `json:"userId"`
	Balance   float64   `json:"balance"`
	UpdatedAt time.Time `json:"updatedAt"`
}

type OrderSide string

const (
	SideBuy  OrderSide = "buy"
	SideSell OrderSide = "sell"
)

type OrderStatus string

const (
	OrderPending   OrderStatus = "pending"
	OrderFilled    OrderStatus = "filled"
	OrderRejected  OrderStatus = "rejected"
	OrderCancelled OrderStatus = "cancelled"
)

type Order struct {
	ID              uuid.UUID   `json:"id"`
	UserID          uuid.UUID   `json:"userId"`
	PlayerSeasonID  int         `json:"playerSeasonId"`
	Side            OrderSide   `json:"side"`
	Quantity        int         `json:"quantity"`
	Price           float64     `json:"price"`
	Total           float64     `json:"total"`
	Status          OrderStatus `json:"status"`
	FilledAt        *time.Time  `json:"filledAt,omitempty"`
	CreatedAt       time.Time   `json:"createdAt"`
}

type Trade struct {
	ID              uuid.UUID `json:"id"`
	OrderID         uuid.UUID `json:"orderId"`
	UserID          uuid.UUID `json:"userId"`
	PlayerSeasonID  int       `json:"playerSeasonId"`
	Side            OrderSide `json:"side"`
	Quantity        int       `json:"quantity"`
	Price           float64   `json:"price"`
	Total           float64   `json:"total"`
	ExecutedAt      time.Time `json:"executedAt"`
}

type Position struct {
	ID              int       `json:"id"`
	UserID          uuid.UUID `json:"userId"`
	PlayerSeasonID  int       `json:"playerSeasonId"`
	Quantity        int       `json:"quantity"`
	AvgCost         float64   `json:"avgCost"`
	UpdatedAt       time.Time `json:"updatedAt"`
}

type IndexType string

const (
	IndexLeague   IndexType = "league"
	IndexTeam     IndexType = "team"
	IndexPosition IndexType = "position"
	IndexMomentum IndexType = "momentum"
)

type Index struct {
	ID                 int       `json:"id"`
	Name               string    `json:"name"`
	IndexType          IndexType `json:"indexType"`
	Description        string    `json:"description,omitempty"`
	TeamID             *int      `json:"teamId,omitempty"`
	TeamAbbreviation   *string   `json:"teamAbbreviation,omitempty"`
	CreatedAt          time.Time `json:"createdAt"`
}

type IndexConstituent struct {
	ID              int       `json:"id"`
	IndexID         int       `json:"indexId"`
	PlayerSeasonID  int       `json:"playerSeasonId"`
	Weight          float64   `json:"weight"`
	UpdatedAt       time.Time `json:"updatedAt"`
}

type IndexHistory struct {
	ID         int       `json:"id"`
	IndexID    int       `json:"indexId"`
	TradeDate  time.Time `json:"tradeDate"`
	Level      float64   `json:"level"`
	PrevLevel  *float64  `json:"prevLevel,omitempty"`
	ChangePct  *float64  `json:"changePct,omitempty"`
	CreatedAt  time.Time `json:"createdAt"`
}

type LeaderboardSnapshot struct {
	ID             int       `json:"id"`
	UserID         uuid.UUID `json:"userId"`
	SnapshotDate   time.Time `json:"snapshotDate"`
	PortfolioValue float64   `json:"portfolioValue"`
	CashBalance    float64   `json:"cashBalance"`
	TotalValue     float64   `json:"totalValue"`
	Rank           *int      `json:"rank,omitempty"`
	CreatedAt      time.Time `json:"createdAt"`

	Username string `json:"username,omitempty"`
}
