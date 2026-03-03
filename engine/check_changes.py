import sys, io, psycopg2
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

conn = psycopg2.connect('postgresql://postgres:4236@localhost:5432/nba_exchange')
cur = conn.cursor()

# What is the latest trade date?
cur.execute("SELECT MAX(trade_date) FROM price_history")
latest = cur.fetchone()[0]
print(f"Latest trade date: {latest}")

# Get the previous trade date
cur.execute("SELECT DISTINCT trade_date FROM price_history ORDER BY trade_date DESC LIMIT 3")
dates = [r[0] for r in cur.fetchall()]
print(f"Last 3 trade dates: {dates}")

# Distribution of change_pct on the latest day
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(*) FILTER (WHERE change_pct > 0) as positive,
        COUNT(*) FILTER (WHERE change_pct = 0 OR change_pct IS NULL) as zero_or_null,
        COUNT(*) FILTER (WHERE change_pct < 0) as negative,
        AVG(change_pct) as avg_chg
    FROM price_history WHERE trade_date = %s
""", (latest,))
row = cur.fetchone()
print(f"\nLatest day ({latest}) change distribution:")
print(f"  Total: {row[0]}, Positive: {row[1]}, Zero/NULL: {row[2]}, Negative: {row[3]}, Avg: {row[4]}")

# Same for the previous day
if len(dates) > 1:
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE change_pct > 0) as positive,
            COUNT(*) FILTER (WHERE change_pct = 0 OR change_pct IS NULL) as zero_or_null,
            COUNT(*) FILTER (WHERE change_pct < 0) as negative,
            AVG(change_pct) as avg_chg
        FROM price_history WHERE trade_date = %s
    """, (dates[1],))
    row = cur.fetchone()
    print(f"Previous day ({dates[1]}) change distribution:")
    print(f"  Total: {row[0]}, Positive: {row[1]}, Zero/NULL: {row[2]}, Negative: {row[3]}, Avg: {row[4]}")

# Jokic last 20 prices to see trend
cur.execute("""
    SELECT ph.trade_date, ph.price, ph.change_pct, ph.perf_score
    FROM price_history ph
    JOIN player_seasons ps ON ph.player_season_id = ps.id
    JOIN players p ON ps.player_id = p.id
    WHERE p.last_name ILIKE '%%joki%%'
    ORDER BY ph.trade_date DESC LIMIT 20
""")
print("\nJokic last 20 entries:")
for row in cur.fetchall():
    chg = f"{float(row[2]):.4f}" if row[2] is not None else "NULL"
    print(f"  {row[0]}  ${float(row[1]):>7.2f}  chg={chg}  perf={float(row[3]):.2f}")

# Check first 5 and last 5 trading days for Jokic
cur.execute("""
    SELECT ph.trade_date, ph.price, ph.perf_score
    FROM price_history ph
    JOIN player_seasons ps ON ph.player_season_id = ps.id
    JOIN players p ON ps.player_id = p.id
    WHERE p.last_name ILIKE '%%joki%%'
    ORDER BY ph.trade_date ASC LIMIT 5
""")
print("\nJokic FIRST 5 entries (season start):")
for row in cur.fetchall():
    print(f"  {row[0]}  ${float(row[1]):>7.2f}  perf={float(row[2]):.2f}")

# Check top 10 by market cap, show their first price vs latest price
print("\nTop 15 players: start price vs current price:")
cur.execute("""
    WITH latest AS (
        SELECT ps.id as ps_id, ph.price, ph.change_pct
        FROM player_seasons ps
        JOIN LATERAL (
            SELECT price, change_pct FROM price_history
            WHERE player_season_id = ps.id ORDER BY trade_date DESC LIMIT 1
        ) ph ON true
    ),
    earliest AS (
        SELECT ps.id as ps_id, ph.price, ph.trade_date
        FROM player_seasons ps
        JOIN LATERAL (
            SELECT price, trade_date FROM price_history
            WHERE player_season_id = ps.id ORDER BY trade_date ASC LIMIT 1
        ) ph ON true
    )
    SELECT p.first_name || ' ' || p.last_name,
           e.price as start_price, l.price as current_price,
           ROUND((l.price - e.price) / NULLIF(e.price, 0) * 100, 2) as total_chg_pct,
           l.change_pct as latest_daily_chg
    FROM latest l
    JOIN earliest e ON l.ps_id = e.ps_id
    JOIN player_seasons ps ON l.ps_id = ps.id
    JOIN players p ON ps.player_id = p.id
    ORDER BY l.price * ps.float_shares DESC LIMIT 15
""")
print(f"  {'Player':<28} {'Start$':>8} {'Now$':>8} {'Total%':>8} {'DayChg':>8}")
print(f"  {'-'*68}")
for name, sp, cp, total, daily in cur.fetchall():
    total_s = f"{float(total):.1f}%" if total else "N/A"
    daily_s = f"{float(daily)*100:.2f}%" if daily is not None else "NULL"
    print(f"  {name:<28} {float(sp):>8.2f} {float(cp):>8.2f} {total_s:>8} {daily_s:>8}")

conn.close()
