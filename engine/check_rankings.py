import sys, io, psycopg2
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

conn = psycopg2.connect('postgresql://postgres:4236@localhost:5432/nba_exchange')
cur = conn.cursor()
cur.execute("""
    SELECT p.first_name || ' ' || p.last_name, ps.tier, ps.float_shares, ph.price,
           ph.price * ps.float_shares as mcap, ph.change_pct
    FROM players p
    JOIN player_seasons ps ON ps.player_id = p.id
    JOIN LATERAL (
        SELECT price, change_pct FROM price_history
        WHERE player_season_id = ps.id ORDER BY trade_date DESC LIMIT 1
    ) ph ON true
    ORDER BY mcap DESC LIMIT 40
""")

header = f"{'#':<4}{'Player':<26}{'Tier':<18}{'Shares':<12}{'Price':>8}{'Chg%':>8}{'Mkt Cap':>15}"
print(header)
print("-" * len(header))
for i, (name, tier, shares, price, mcap, chg) in enumerate(cur.fetchall(), 1):
    chg_str = f"{float(chg):.2f}%" if chg else "N/A"
    print(f"{i:<4}{name:<26}{tier:<18}{shares:<12}{float(price):>8.2f}{chg_str:>8}{float(mcap):>15,.0f}")
conn.close()
