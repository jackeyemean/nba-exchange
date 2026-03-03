import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from nba_api.stats.static import players

names = [
    "Stephen Curry", "Domantas Sabonis", "Karl-Anthony Towns", "Trae Young",
    "Ivica Zubac", "Tyler Herro", "Evan Mobley", "Amen Thompson",
    "Josh Giddey", "Trey Murphy", "Lauri Markkanen", "Jalen Johnson",
    "Scottie Barnes", "Austin Reaves", "Nikola Vucevic",
    "Keyonte George", "Joel Embiid", "Dejounte Murray",
    "Kevin Porter Jr", "Peyton Watson", "Naji Marshall",
    "Reed Sheppard", "Neemias Queta", "Alijah Martin", "Chaz Lanier",
]
all_p = players.get_players()
for n in names:
    m = [p for p in all_p if n.lower() in p["full_name"].lower()]
    if not m and " " in n:
        first, last = n.split(" ", 1)
        m = [p for p in all_p if first.lower() in p["first_name"].lower() and last.lower() in p["last_name"].lower()]
    if m:
        print(f'"{m[0]["id"]}": "{m[0]["full_name"]}"')
    else:
        print(f"NOT FOUND: {n}")
