import logging
import time
from datetime import datetime

from nba_api.stats.endpoints import (
    CommonAllPlayers,
    CommonPlayerInfo,
    LeagueStandings,
    ScoreboardV2,
    BoxScoreTraditionalV2,
)
from nba_api.stats.static import teams as nba_teams

import db

log = logging.getLogger(__name__)

FLOAT_SHARES = {
    "magnificent_7": 10_000_000,
    "blue_chip": 8_000_000,
    "growth": 6_400_000,
    "mid_cap": 5_120_000,
    "penny_stock": 2_560_000,
}

REQUEST_DELAY = 0.6


def _nba_season_string(label: str) -> str:
    """Convert '2025-26' to '2025-26' (nba_api expects this format)."""
    return label


def _safe_request(endpoint_cls, **kwargs):
    time.sleep(REQUEST_DELAY)
    return endpoint_cls(**kwargs)


def sync_teams(conn, season_label: str):
    log.info("Syncing teams for season %s", season_label)
    all_teams = nba_teams.get_teams()
    for t in all_teams:
        db.upsert_team(
            conn,
            external_id=str(t["id"]),
            name=t["full_name"],
            abbreviation=t["abbreviation"],
            city=t["city"],
        )
    conn.commit()
    log.info("Synced %d teams", len(all_teams))


def _classify_tier(avg_minutes: float) -> str:
    """Fallback tier classification for live sync (backfill uses perf-based ranking)."""
    if avg_minutes >= 32:
        return "blue_chip"
    if avg_minutes >= 26:
        return "growth"
    if avg_minutes >= 20:
        return "mid_cap"
    return "penny_stock"


def sync_players(conn, season_label: str):
    log.info("Syncing players for season %s", season_label)
    season = db.get_season_by_label(conn, season_label)
    if not season:
        log.error("Season %s not found", season_label)
        return

    resp = _safe_request(CommonAllPlayers, league_id="00", season=season_label, is_only_current_season=1)
    players_df = resp.get_data_frames()[0]

    count = 0
    for _, row in players_df.iterrows():
        external_id = str(row["PERSON_ID"])
        display_name = row.get("DISPLAY_FIRST_LAST", "")
        parts = display_name.split(" ", 1) if display_name else ["", ""]
        first_name = parts[0] if len(parts) > 0 else ""
        last_name = parts[1] if len(parts) > 1 else ""

        if not first_name and not last_name:
            continue

        player_id = db.upsert_player(conn, external_id=external_id, first_name=first_name, last_name=last_name)

        team_ext_id = str(row.get("TEAM_ID", "0"))
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM teams WHERE external_id = %s", (team_ext_id,))
            team_row = cur.fetchone()
        if not team_row:
            continue

        team_id = team_row[0]

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(AVG(minutes), 0)
                FROM game_stats gs
                JOIN player_seasons ps ON gs.player_season_id = ps.id
                WHERE ps.player_id = %s AND ps.season_id = %s
                """,
                (player_id, season["id"]),
            )
            avg_min = float(cur.fetchone()[0])

        tier = _classify_tier(avg_min)
        float_shares = FLOAT_SHARES[tier]

        db.upsert_player_season(conn, player_id=player_id, season_id=season["id"],
                                team_id=team_id, tier=tier, float_shares=float_shares)
        count += 1

    conn.commit()
    log.info("Synced %d players", count)


def sync_standings(conn, season_label: str):
    log.info("Syncing standings for season %s", season_label)
    season = db.get_season_by_label(conn, season_label)
    if not season:
        log.error("Season %s not found", season_label)
        return

    resp = _safe_request(LeagueStandings, league_id="00", season=season_label, season_type="Regular Season")
    df = resp.get_data_frames()[0]

    count = 0
    for _, row in df.iterrows():
        team_ext_id = str(row["TeamID"])
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM teams WHERE external_id = %s", (team_ext_id,))
            team_row = cur.fetchone()
        if not team_row:
            continue

        wins = int(row.get("WINS", 0))
        losses = int(row.get("LOSSES", 0))
        win_pct = float(row.get("WinPCT", 0.0))

        db.upsert_team_standings(conn, team_id=team_row[0], season_id=season["id"],
                                 wins=wins, losses=losses, win_pct=win_pct)
        count += 1

    conn.commit()
    log.info("Synced standings for %d teams", count)


def _compute_ts_pct(pts: int, fga: int, fta: int) -> float:
    tsa = fga + 0.44 * fta
    if tsa == 0:
        return 0.0
    return pts / (2.0 * tsa)


def _compute_raw_perf(pts, fgm, fga, ftm, fta, fg3m, fg3a,
                      oreb, dreb, ast, stl, blk, tov) -> float:
    fgmi = fga - fgm
    ftmi = fta - ftm
    fg3mi = fg3a - fg3m
    return (
        (pts * 1.0)
        + (fgm * 0.5) + (fgmi * -0.5)
        + (ftm * 1.0) + (ftmi * -1.0)
        + (fg3m * 2.0) + (fg3mi * -1.0)
        + (oreb * 1.5) + (dreb * 1.0)
        + (ast * 2.0)
        + (stl * 2.0) + (blk * 2.0)
        + (tov * -1.0)
    )


def sync_game_stats(conn, season_label: str, game_date: str):
    log.info("Syncing game stats for %s on %s", season_label, game_date)
    season = db.get_season_by_label(conn, season_label)
    if not season:
        log.error("Season %s not found", season_label)
        return

    resp = _safe_request(ScoreboardV2, game_date=game_date, league_id="00")
    games_df = resp.get_data_frames()[0]

    if games_df.empty:
        log.info("No games found for %s", game_date)
        return

    game_ids = games_df["GAME_ID"].unique().tolist()
    count = 0

    for game_id in game_ids:
        try:
            box = _safe_request(BoxScoreTraditionalV2, game_id=game_id)
            player_stats = box.get_data_frames()[0]
        except Exception:
            log.exception("Failed to fetch box score for game %s", game_id)
            continue

        for _, row in player_stats.iterrows():
            player_ext_id = str(row["PLAYER_ID"])

            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT ps.id FROM player_seasons ps
                    JOIN players p ON ps.player_id = p.id
                    WHERE p.external_id = %s AND ps.season_id = %s
                    """,
                    (player_ext_id, season["id"]),
                )
                ps_row = cur.fetchone()

            if not ps_row:
                continue

            minutes_str = row.get("MIN", "0") or "0"
            try:
                if ":" in str(minutes_str):
                    parts = str(minutes_str).split(":")
                    minutes = float(parts[0]) + float(parts[1]) / 60.0
                else:
                    minutes = float(minutes_str)
            except (ValueError, TypeError):
                minutes = 0.0

            pts = int(row.get("PTS", 0) or 0)
            ast = int(row.get("AST", 0) or 0)
            reb = int(row.get("REB", 0) or 0)
            stl = int(row.get("STL", 0) or 0)
            blk = int(row.get("BLK", 0) or 0)
            tov = int(row.get("TO", 0) or 0)
            fgm = int(row.get("FGM", 0) or 0)
            fga = int(row.get("FGA", 0) or 0)
            ftm = int(row.get("FTM", 0) or 0)
            fta = int(row.get("FTA", 0) or 0)
            fg3m = int(row.get("FG3M", 0) or 0)
            fg3a = int(row.get("FG3A", 0) or 0)
            oreb = int(row.get("OREB", 0) or 0)
            dreb = int(row.get("DREB", 0) or 0)

            ts_pct = _compute_ts_pct(pts, fga, fta)
            raw_perf = _compute_raw_perf(
                pts, fgm, fga, ftm, fta, fg3m, fg3a,
                oreb, dreb, ast, stl, blk, tov,
            )

            db.upsert_game_stat(
                conn,
                player_season_id=ps_row[0],
                game_date=game_date,
                external_game_id=str(game_id),
                minutes=minutes,
                pts=pts, ast=ast, reb=reb, stl=stl, blk=blk, tov=tov,
                fgm=fgm, fga=fga, ftm=ftm, fta=fta,
                fg3m=fg3m, fg3a=fg3a, oreb=oreb, dreb=dreb,
                raw_perf_score=raw_perf,
                ts_pct=ts_pct,
            )
            count += 1

    conn.commit()
    log.info("Synced %d player game stat rows", count)


def sync_player_info(conn, player_external_id: str):
    log.info("Syncing player info for %s", player_external_id)
    resp = _safe_request(CommonPlayerInfo, player_id=player_external_id)
    df = resp.get_data_frames()[0]

    if df.empty:
        log.warning("No info found for player %s", player_external_id)
        return

    row = df.iloc[0]
    birthdate_str = row.get("BIRTHDATE", None)
    birthdate = None
    if birthdate_str:
        try:
            birthdate = datetime.strptime(str(birthdate_str)[:10], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            pass

    position = row.get("POSITION", None)
    height = row.get("HEIGHT", None)
    weight_raw = row.get("WEIGHT", None)
    weight = int(weight_raw) if weight_raw else None

    db.upsert_player(
        conn,
        external_id=player_external_id,
        first_name=row.get("FIRST_NAME", ""),
        last_name=row.get("LAST_NAME", ""),
        birthdate=birthdate,
        position=position,
        height=height,
        weight=weight,
    )
    conn.commit()
