import psycopg2
conn = psycopg2.connect('postgresql://postgres:4236@localhost:5432/nba_exchange')
cur = conn.cursor()
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(birthdate) as with_birthdate,
        COUNT(*) - COUNT(birthdate) as null_birthdate
    FROM players p
    JOIN player_seasons ps ON ps.player_id = p.id
    WHERE ps.season_id = 1
""")
row = cur.fetchone()
print(f"Season players: {row[0]} total, {row[1]} with birthdate, {row[2]} NULL")
conn.close()
