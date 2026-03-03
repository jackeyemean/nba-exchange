# How Hoop Exchange Works

Hoop Exchange is a fan-built simulation stock exchange where every basketball player in the current season is a tradeable stock. There is no real money involved — this is purely a game for fans who want to engage with the sport through a financial lens.

---

## The Big Picture

Every player is a stock. You buy and sell shares at the current **share price**. Each player has a fixed number of **float shares** for the season. Their **market cap** = share price × float shares. Market cap determines leaderboard rankings and who "overtakes" whom — a player with a higher market cap ranks above a player with a lower one, even if the lower player has a higher share price (because they have fewer shares).

---

## Share Price vs. Float Shares vs. Market Cap

| Concept | What It Is |
|---------|------------|
| **Share Price** | The dollar amount you pay per share when buying (or receive when selling). Changes every trading day based on performance, age, team wins, and injury status. |
| **Float Shares** | The total number of shares that exist for that player. **Fixed for the entire season** — determined by their tier (see below). Does not change mid-season. |
| **Market Cap** | Share price × float shares. The "total value" of the player stock. This is what we rank by. |

**Example:** Player A has 10M shares at $50 → market cap = $500M. Player B has 2.56M shares at $120 → market cap = $307M. Player A ranks higher despite a lower share price because they have more shares, this is to reward players with a reputation that have done well before.

---

## What Drives Share Price? (In Order of Impact)

1. **Raw performance score** — The single biggest driver. Stats (points, assists, steals, etc.) are combined into one number per game (ESPN fantasy–aligned). Elite performers typically score 45–55 per game; bench players 10–25. This flows through a power curve to set the base price.
2. **Power-law scaling** — A score of 80 is worth far more than 2× a score of 40. The exponent (1.5) creates a steep curve: small stat improvements at the top move the price a lot.
3. **Recent performance** — The last 10 games are weighted 25% vs. 75% season average. Hot/cold streaks move the needle.
4. **Prior-season blend** — For the first 10 games, prior-year performance is blended in. Players who haven't played yet start at 100% prior-year value.
5. **Age multiplier** — Young high performers get a boost (up to 1.40×); older low performers get a tax (down to 0.70×). Prime (28–32) = 1.00×.
6. **Team win%** — Linear by league rank: best team 1.10×, worst team 0.95× (capped +10% / −5%).
7. **Injury/availability** — Consecutive missed games reduce the multiplier (down to 0.70× at 30+ games missed).

---

## Raw Performance Score

The raw score is a weighted sum of 13 stat categories, aligned with ESPN fantasy basketball scoring for correlation with familiar fantasy values. Made shots add, missed shots subtract. Assists, steals, and blocks are weighted heavily.

| Stat | Weight | Stat | Weight |
|------|--------|------|--------|
| Points (PTS) | +1.0 | Offensive Rebounds (OREB) | +1.0 |
| Field Goals Made (FGM) | +1.0 | Defensive Rebounds (DREB) | +1.0 |
| Field Goals Missed (FGA−FGM) | −1.0 | Assists (AST) | +2.0 |
| Free Throws Made (FTM) | +1.0 | Steals (STL) | +3.0 |
| Free Throws Missed (FTA−FTM) | −1.0 | Blocks (BLK) | +3.0 |
| 3-Pointers Made (3PM) | +1.0 | Turnovers (TOV) | −2.0 |

**Design notes:** Rebounds (OREB + DREB) and scoring (PTS, FGM, FTM, 3PM) with miss penalties reward efficiency. Assists, steals, and blocks are weighted 2–3× to reflect playmaking and defensive impact. Turnovers are penalized −2 to match ESPN fantasy.

---

## Full Example: Victor Wembanyama

Walk through one player’s price calculation step by step.

### Step 1: Raw performance (one game)

Typical Wemby line: 22 pts, 8 FGM, 18 FGA, 5 FTM, 7 FTA, 1 3PM, 2 OREB, 9 DREB, 3.5 AST, 1 STL, 3.5 BLK, 3 TOV.

```
raw = (22×1) + (8×1) + (10×−1) + (5×1) + (2×−1) + (1×1) + (2×1) + (9×1) + (3.5×2) + (1×3) + (3.5×3) + (3×−2)
    = 22 + 8 − 10 + 5 − 2 + 1 + 2 + 9 + 7 + 3 + 10.5 − 6
    = 49.5 per game
```

### Step 2: Blending (season + recent form)

Assume 30 games played. Season avg raw = 48, last 10 games avg = 52 (hot streak).

```
blended_raw = 0.75 × 48 + 0.25 × 52 = 36 + 13 = 49.0
```

### Step 3: Base price (power curve)

```
perf_score = 49.0
normalized = 49.0 / 100 = 0.49
base_price = (0.49 ^ 1.5) × $275 ≈ 0.343 × 275 ≈ $94.33
```

### Step 4: Multipliers

- **Age:** 21 years old, 7 years below prime. Elite performer (top of league that day) → norm = 1.0.
  - Pure: +0.7% × 7 = 4.9%
  - Perf-scaled: +5.5% × 7 × 1.0 = 38.5%
  - age_mult = 1.0 + 0.049 + 0.385 = 1.434 → **capped at 1.40×**
- **Team win%:** Spurs at 45% → rank ~25 of 30 → **~0.97×** (linear 0.95–1.10)
- **Injury:** 0 missed → **1.00×**

### Step 5: Final price

```
share_price = $94.33 × 1.40 × 0.97 × 1.00 ≈ $128.10
```

If Wemby is Mag 7 (10M float): market_cap = $128.10 × 10,000,000 = **~$1.28B**.

### Methodology assessment

| Aspect | Assessment |
|--------|------------|
| **Raw score** | ESPN-aligned weights give familiar fantasy-like values and reward efficiency (miss penalties) and defense (steals/blocks). |
| **Blending** | 75/25 season vs last 10 games balances stability with hot/cold streaks. Prior-year blend for early season avoids noisy starts. |
| **Power curve** | Exponent 1.5 makes small stat gains at the top matter more than at the bottom, matching how fans value stars. |
| **Age multiplier** | Young elite players reach 1.4×; older low performers drop toward 0.7×. Prime (28–32) is neutral. |
| **Win%** | Linear 0.95×–1.10× by league rank; capped ±10% / −5% so team context stays modest. |
| **Injury** | Quadratic ramp down to 0.70× over 30 missed games models increasing uncertainty. |

Overall, the formula prioritizes performance, uses age and team context as modifiers, and keeps injury as a separate discount.

---

## Blending: Season Average + Recent Form + Prior Year

The raw score is not computed from a single source. It's blended from three signals:

### 1. Season Average (75% weight when playing)

All games played so far this season, averaged. This is the baseline.

### 2. Recent Form (25% weight)

The **last 10 games** only. If a player was injured and only played 6 of those 10, we use those 6. This captures hot and cold streaks.

```
blended_raw = 0.75 × season_avg_raw + 0.25 × recent_10_raw
```

A player on a hot streak will have recent_raw > season_avg_raw, so their blended score (and price) rises. A cold streak does the opposite.

### 3. Prior-Season Blend (first 10 games only)

For the first 10 games of the season, prior-year performance is blended in:

- **0 games played:** 100% prior-year, 0% current
- **5 games played:** 50% prior-year, 50% current (blended)
- **10+ games played:** 0% prior-year, 100% current

Players who haven't played yet (e.g., injured to start the year) use 100% prior-year until they play.

---

## Base Price: Power-Law Scaling

The blended raw score becomes a base price via:

```
perf_score = max(0.5, blended_raw)
normalized = perf_score / 100
base_price = (normalized ^ 1.5) × $275
```

- **No cap** — Scores above 100 (theoretical) would exceed $275 base price
- **PRICE_EXPONENT = 1.5** — creates a steep curve
- **$275** — a normalized score of 1.0 (raw = 100) yields $275 base price; typical elite raw 50 → ~$97

**Rough examples:** (Raw scores are typically 15–55 per game; elite players often 45–55.)

| Raw Score | Normalized | Base Price |
|-----------|------------|------------|
| 55 | 0.55 | ~$107 |
| 50 | 0.50 | ~$97 |
| 35 | 0.35 | ~$57 |
| 20 | 0.20 | ~$25 |
| 10 | 0.10 | ~$9 |

The exponent makes the curve steep: going from 50→55 has a bigger dollar impact than 20→25.

---

## Multipliers (Applied to Base Price)

### Age Multiplier (0.70× — 1.40×)

- **Prime (28–32):** 1.00× — no change
- **Younger than 28:** Boost. Two parts:
  - **Pure:** +0.7% per year below prime
  - **Performance-scaled:** +5.5% per year × (perf/100). Elite young players (Flagg, Wemby, etc.) reach the 1.40× ceiling; bench players get a smaller boost.
- **Older than 32:** Tax. Two parts:
  - **Pure:** −2.6% per year above prime
  - **Performance-scaled:** −4.0% per year × (1 − perf/100). A 35-year-old struggling gets a bigger tax than a 35-year-old still performing.
- **Cap:** Age 38+ treated as 38. Floor 0.70×, ceiling **1.40×** for young high performers.

### Team Win% Multiplier (0.90× — 1.15×)

Win% is computed as-of each trading day from games played so far. Multiplier is **linear by league rank** (relative to all 30 teams):

- **Best team:** 1.15× (+15% cap)
- **Worst team:** 0.90× (−10% cap)
- **Linear interpolation** between rank 1 (worst) and rank 30 (best)

This keeps team context modest: a 25-point spread across the league, so individual performance remains the main driver.

### Injury / Availability Multiplier (0.70× — 1.00×)

Consecutive missed games reduce the multiplier:

- **0 missed:** 1.00×
- **1–29 missed:** Quadratic ramp. Early games have a small impact; it steepens toward 30.
- **30+ missed:** **Capped at 0.70×** (30% penalty). 50 games missed = same as 30.

"Consecutive missed" is inferred from days since last game (≈ 2 days per game in the schedule).

---

## Final Share Price Formula

```
share_price = base_price × age_mult × win_pct_mult × injury_mult
```

Minimum price is $0.01.

---

## Float Shares and Tiers

Each player's float shares are **fixed for the season** and determined by their **tier**. Tiers are assigned at the start of the season based on end-of-prior-season performance (or draft position for rookies). They do not change mid-season.

| Tier | Float Shares | Assignment |
|------|--------------|------------|
| Magnificent 7 | 10,000,000 | Top 7 by prior-year price |
| Blue Chip | 8,000,000 | Ranks 8–40 |
| Growth | 6,400,000 | Ranks 41–150 |
| Mid Cap | 5,120,000 | Ranks 151–250 |
| Penny Stock | 2,560,000 | Everyone else |

**Rookies** (first season): Lottery (1–14) → Growth; first round/early second (15–39) → Mid Cap; else → Penny Stock.

---

## Tier Bootstrap: How the Simulation Runs

Tiers are built from historical performance. The full methodology runs in two phases:

### Phase 1: Prior Two Seasons (2023–24, 2024–25) — Uniform Shares

- **Float shares:** All players get the same 5M shares (no tier variation).
- **Full methodology:** Raw performance, blending (season + last 10 + prior-year), power curve, age multiplier, win% multiplier, injury multiplier — all applied.
- **Purpose:** Build a clean performance ranking. End-of-2024–25 price ranking determines tier assignment for the current season.

### Phase 2: Current Season (2025–26) — Tier-Based Shares

- **Float shares:** Tiers from Phase 1 (Mag 7, Blue Chip, Growth, Mid Cap, Penny Stock) with tier-specific shares.
- **Full methodology:** Same formula as Phase 1 — raw perf, blending, power curve, age, win%, injury.
- **Rookies:** Tiers from draft position (lottery → Growth, etc.) instead of prior-year ranking.

Market cap = price × float shares, so tier-based shares amplify the impact of price changes for higher-tier players.

---

## Market Cap

```
market_cap = share_price × float_shares
```

Market cap is what we rank by. A Mag 7 player with a declining price can be overtaken by a Growth player with a rising price — the Growth player needs a higher share price to compensate for fewer shares.

### Tier Mobility (Price Premium Needed)

To match the market cap of a player in the tier above you, you need this much higher share price:

| Your Tier → Tier Above | Price Premium |
|------------------------|---------------|
| Penny Stock → Mid Cap | 2× |
| Mid Cap → Growth | 1.25× |
| Growth → Blue Chip | 1.25× |
| Blue Chip → Mag 7 | 1.25× |

---

## Trading Days and Game Inclusion

- **Trading days:** Weekdays only (Monday–Friday). Prices update once per trading day.
- **Games included:** For a given trading day, we include **all games** with `game_date ≤ trade_date`. Weekend games are included — they roll into the next weekday's price.

---

## Market Hours

Prices update at **market open** each weekday. Trading hours: 9:30 AM – 5:00 PM ET. No trading during live games.

---

## Disclaimer

Hoop Exchange is a fan simulation. No real currency is involved. This platform is not affiliated with, endorsed by, or connected to any professional basketball league, team, or players association.
