# How Hoop Exchange Works

Hoop Exchange is a fan-built simulation stock exchange where every basketball player in the current season is a tradeable stock. There is no real money involved -- this is purely a game for fans who want to engage with the sport through a financial lens.

---

## Performance Score

Every player's stock price starts with a **Performance Score** calculated from their per-game averages using 13 stat categories:

| Stat | Weight | Stat | Weight |
|------|--------|------|--------|
| Points (PTS) | +1.0 | Offensive Rebounds (OREB) | +1.5 |
| Field Goals Made (FGM) | +0.5 | Defensive Rebounds (DREB) | +1.0 |
| Field Goals Missed | -0.5 | Assists (AST) | +2.0 |
| Free Throws Made (FTM) | +1.0 | Steals (STL) | +2.0 |
| Free Throws Missed | -1.0 | Blocks (BLK) | +2.0 |
| Three Pointers Made (3PM) | +2.0 | Turnovers (TOV) | -1.0 |
| Three Pointers Missed | -1.0 | | |

"Missed" stats are derived: Field Goals Missed = FGA - FGM, and so on.

Assists, steals, and blocks are weighted at 2x, rewarding playmaking and two-way impact. Made shots are rewarded while misses are penalized, capturing efficiency without needing a separate efficiency metric.

### Blending

The raw performance score is blended from three signals:

- **Season average** -- all games played so far
- **Recent form (last 20 games)** -- always weighted at 40%. We always use the last 20-game window; if a player was injured and only played 10 of those 20 games, we use those 10 games for their recent form average. Hot/cold streaks move the price.
- **Prior-year performance** -- smoothly fades out over the first 20 games of the season. A player who hasn't played yet starts at 100% prior-year value. By game 20, prior-year influence drops to zero.

---

## Stock Price

The blended performance score is converted to a stock price using **power-law scaling**:

```
base_price = (perf_score / 100) ^ 2.5 x $275
```

The exponent of 2.5 creates a steep curve: elite players command prices in the hundreds, while low performers trade in single digits or pennies. This mirrors real stock markets where top companies vastly outprice small caps.

### Multipliers

Two multipliers are applied on top of the base price:

**Age Multiplier (0.70x -- 1.25x)**

- Players aged 28--32 are in their **prime years** with no boost or penalty (1.00x).
- Younger players receive a year-by-year boost that scales with their performance -- a 20-year-old stat stuffer gets a bigger boost than a 20-year-old bench player.
- Older players receive a year-by-year tax. The aging penalty caps at age 38 (anyone older is treated the same as 38).

**Injury / Availability Multiplier (0.70x -- 1.00x)**

When a player misses consecutive games, a penalty ramps up gradually:

- 1 missed game: tiny penalty (~0.03%)
- The penalty follows a quadratic curve, getting steeper the more games missed
- Maximum penalty: **30%** (0.70x multiplier) reached at 30 consecutive missed games
- After 30 games missed, the penalty freezes -- the price stabilizes as a "prediction" of what the player will be worth when they return

This means load management (missing 1--2 games) barely affects the stock, but a serious injury causes a meaningful decline over time.

### Final Price

```
stock_price = base_price x age_mult x injury_mult
```

---

## Shares and Market Cap

Each player stock has a fixed number of **float shares** for the season, determined by their tier from the **prior season**:

| Tier | Shares | How Assigned |
|------|--------|--------------|
| Magnificent 7 | 10,000,000 | Top 7 players by prior-year performance |
| Blue Chip | 8,500,000 | Players ranked 8--30 |
| Growth | 7,000,000 | Upper performance tier below top 30 |
| Mid Cap | 5,000,000 | Middle performance tier |
| Small Cap | 3,000,000 | Lower performance tier |
| Penny Stock | 500,000 | Remaining players |

**Market Cap = Stock Price x Float Shares**

This is the key mechanic: a player's tier (and shares) are locked from last year's performance, but their price changes daily based on *this year's* performance. This creates real dynamics:

- A Mag 7 player from last year who gets injured will still have 10M shares but a declining price -- their market cap drops, and Blue Chip players with fewer shares but better current performance can overtake them.
- A breakout player on a Growth tier (7M shares) putting up elite numbers will have a high price but their lower share count acts as a handicap. To match a Mag 7 player in market cap, their price needs to be about 43% higher.

---

## Tiers

The tier badge you see on the Discover page represents the player's **prior-season classification**, which determines their share count for the current season. It does *not* update mid-season.

For the **first season** of Hoop Exchange, tiers were initialized manually for key players, with rookies assigned by draft position (lottery picks → Growth, etc.) and the rest ranked by current-season price.

At the **end of the season**, all tiers are recalculated based on that season's performance, and shares are redistributed for the next season. A player who broke out from Growth to top-7 performance would be promoted to Magnificent 7 with 10M shares the following year.

### Tier Mobility (Price Premium Needed)

To overtake a player in the tier above you by market cap, you need a higher stock price to compensate for having fewer shares:

| Your Tier -> Tier Above | Price Premium Needed |
|--------------------------|---------------------|
| Penny Stock -> Small Cap | 6x |
| Small Cap -> Mid Cap | 1.67x |
| Mid Cap -> Growth | 1.40x |
| Growth -> Blue Chip | 1.21x |
| Blue Chip -> Mag 7 | 1.18x |

---

## Market Hours

Prices are updated at **market open** each weekday (Monday--Friday). The market is closed on weekends and holidays.

Trading hours: **9:30 AM -- 5:00 PM ET** on weekdays. No trading is allowed during live games.

---

## Disclaimer

Hoop Exchange is a fan simulation. No real currency is involved. This platform is not affiliated with, endorsed by, or connected to any professional basketball league, team, or players association.
