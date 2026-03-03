"""Quick script to verify prior-year tier assignments with availability + age multiplier."""
import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from nba_api.stats.endpoints import LeagueDashPlayerStats
from pricing.formula import calculate_raw_perf, get_age_multiplier_from_age

FULL_SEASON_GP = 65
SEASON = "2024-25"

print(f"Fetching {SEASON} per-game stats...")
resp = LeagueDashPlayerStats(season=SEASON, season_type_all_star="Regular Season", per_mode_detailed="PerGame")
time.sleep(1)
df = resp.get_data_frames()[0]

results = []
for _, r in df.iterrows():
    pid = str(r["PLAYER_ID"])
    name = r["PLAYER_NAME"]
    gp = int(r.get("GP", 0) or 0)
    age = float(r.get("AGE", 0) or 0)
    pts = float(r.get("PTS", 0) or 0)
    fgm = float(r.get("FGM", 0) or 0)
    fga = float(r.get("FGA", 0) or 0)
    ftm = float(r.get("FTM", 0) or 0)
    fta = float(r.get("FTA", 0) or 0)
    fg3m = float(r.get("FG3M", 0) or 0)
    fg3a = float(r.get("FG3A", 0) or 0)
    oreb = float(r.get("OREB", 0) or 0)
    dreb = float(r.get("DREB", 0) or 0)
    ast = float(r.get("AST", 0) or 0)
    stl = float(r.get("STL", 0) or 0)
    blk = float(r.get("BLK", 0) or 0)
    tov = float(r.get("TOV", 0) or 0)
    raw = calculate_raw_perf(pts, fgm, fga, ftm, fta, fg3m, fg3a, oreb, dreb, ast, stl, blk, tov)
    avail = min(1.0, gp / FULL_SEASON_GP)
    age_mult = get_age_multiplier_from_age(age, raw)
    adjusted = raw * avail * age_mult
    results.append((name, pid, gp, age, raw, avail, age_mult, adjusted))

results.sort(key=lambda x: x[7], reverse=True)

print(f"\n{'Rank':<5} {'Player':<25} {'Age':<5} {'GP':<5} {'RawPerf':<9} {'Avail':<7} {'AgeMult':<8} {'Final':<9} {'Tier'}")
print("-" * 95)
for i, (name, pid, gp, age, raw, avail, age_m, adj) in enumerate(results[:50], 1):
    if i <= 7:
        tier = "Mag 7"
    elif i <= 30:
        tier = "Blue Chip"
    elif i <= 100:
        tier = "Growth"
    elif i <= 200:
        tier = "Mid Cap"
    elif i <= 350:
        tier = "Small Cap"
    else:
        tier = "Penny"
    print(f"{i:<5} {name:<25} {age:<5.0f} {gp:<5} {raw:<9.2f} {avail:<7.3f} {age_m:<8.3f} {adj:<9.2f} {tier}")
