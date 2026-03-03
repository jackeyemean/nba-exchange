import psycopg2
conn = psycopg2.connect('postgresql://postgres:4236@localhost:5432/nba_exchange')
cur = conn.cursor()
cur.execute("SELECT tier, COUNT(*) FROM player_seasons WHERE season_id = 1 AND status NOT IN ('delisting','delisted') GROUP BY tier ORDER BY tier")
for row in cur.fetchall():
    print(f"{row[0]}: {row[1]}")
conn.close()
