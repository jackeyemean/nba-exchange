import logging
from contextlib import contextmanager

from config import get_db_connection

log = logging.getLogger(__name__)


@contextmanager
def get_connection():
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_active_season(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT id, label, start_date, end_date, is_active FROM seasons WHERE is_active = TRUE LIMIT 1")
        row = cur.fetchone()
        if not row:
            return None
        return {"id": row[0], "label": row[1], "start_date": row[2], "end_date": row[3], "is_active": row[4]}


def get_season_by_label(conn, label: str):
    with conn.cursor() as cur:
        cur.execute("SELECT id, label, start_date, end_date, is_active FROM seasons WHERE label = %s", (label,))
        row = cur.fetchone()
        if not row:
            return None
        return {"id": row[0], "label": row[1], "start_date": row[2], "end_date": row[3], "is_active": row[4]}


def upsert_team(conn, external_id: str, name: str, abbreviation: str, city: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO teams (external_id, name, abbreviation, city)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (external_id) DO UPDATE SET name = EXCLUDED.name,
                abbreviation = EXCLUDED.abbreviation, city = EXCLUDED.city
            RETURNING id
            """,
            (external_id, name, abbreviation, city),
        )
        return cur.fetchone()[0]


def upsert_player(conn, external_id: str, first_name: str, last_name: str,
                   birthdate=None, position=None, height=None, weight=None) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO players (external_id, first_name, last_name, birthdate, position, height, weight)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (external_id) DO UPDATE SET
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                birthdate = COALESCE(EXCLUDED.birthdate, players.birthdate),
                position = COALESCE(EXCLUDED.position, players.position),
                height = COALESCE(EXCLUDED.height, players.height),
                weight = COALESCE(EXCLUDED.weight, players.weight)
            RETURNING id
            """,
            (external_id, first_name, last_name, birthdate, position, height, weight),
        )
        return cur.fetchone()[0]


def upsert_player_season(conn, player_id: int, season_id: int, team_id: int,
                          tier: str = "bench", float_shares: int = 1_000_000) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO player_seasons (player_id, season_id, team_id, tier, float_shares)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (player_id, season_id) DO UPDATE SET
                team_id = EXCLUDED.team_id,
                tier = EXCLUDED.tier,
                float_shares = EXCLUDED.float_shares
            RETURNING id
            """,
            (player_id, season_id, team_id, tier, float_shares),
        )
        return cur.fetchone()[0]


def upsert_game_stat(conn, player_season_id: int, game_date, external_game_id: str,
                      minutes: float, pts: int, ast: int, reb: int, stl: int, blk: int,
                      tov: int, fgm: int, fga: int, ftm: int, fta: int,
                      raw_perf_score: float, ts_pct: float) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO game_stats
                (player_season_id, game_date, external_game_id, minutes,
                 pts, ast, reb, stl, blk, tov, fgm, fga, ftm, fta,
                 raw_perf_score, ts_pct)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (player_season_id, external_game_id) DO UPDATE SET
                minutes = EXCLUDED.minutes,
                pts = EXCLUDED.pts, ast = EXCLUDED.ast, reb = EXCLUDED.reb,
                stl = EXCLUDED.stl, blk = EXCLUDED.blk, tov = EXCLUDED.tov,
                fgm = EXCLUDED.fgm, fga = EXCLUDED.fga, ftm = EXCLUDED.ftm, fta = EXCLUDED.fta,
                raw_perf_score = EXCLUDED.raw_perf_score, ts_pct = EXCLUDED.ts_pct
            RETURNING id
            """,
            (player_season_id, game_date, external_game_id, minutes,
             pts, ast, reb, stl, blk, tov, fgm, fga, ftm, fta,
             raw_perf_score, ts_pct),
        )
        return cur.fetchone()[0]


def upsert_team_standings(conn, team_id: int, season_id: int, wins: int, losses: int, win_pct: float):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO team_standings (team_id, season_id, wins, losses, win_pct, updated_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            ON CONFLICT (team_id, season_id) DO UPDATE SET
                wins = EXCLUDED.wins, losses = EXCLUDED.losses,
                win_pct = EXCLUDED.win_pct, updated_at = NOW()
            """,
            (team_id, season_id, wins, losses, win_pct),
        )


def upsert_player_salary(conn, player_id: int, season_id: int, salary: int, percentile: float):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO player_salaries (player_id, season_id, salary, percentile, updated_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (player_id, season_id) DO UPDATE SET
                salary = EXCLUDED.salary, percentile = EXCLUDED.percentile, updated_at = NOW()
            """,
            (player_id, season_id, salary, percentile),
        )


def get_player_by_external_id(conn, external_id: str):
    with conn.cursor() as cur:
        cur.execute("SELECT id, external_id, first_name, last_name, birthdate, position FROM players WHERE external_id = %s", (external_id,))
        row = cur.fetchone()
        if not row:
            return None
        return {"id": row[0], "external_id": row[1], "first_name": row[2], "last_name": row[3], "birthdate": row[4], "position": row[5]}


def get_player_by_name(conn, first_name: str, last_name: str):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, external_id, first_name, last_name FROM players WHERE LOWER(first_name) = LOWER(%s) AND LOWER(last_name) = LOWER(%s)",
            (first_name, last_name),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {"id": row[0], "external_id": row[1], "first_name": row[2], "last_name": row[3]}


def insert_price_history(conn, player_season_id: int, trade_date, perf_score: float,
                          age_mult: float, win_pct_mult: float, salary_eff_mult: float,
                          raw_score: float, price: float, market_cap: float,
                          prev_price: float | None, change_pct: float | None):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO price_history
                (player_season_id, trade_date, perf_score, age_mult, win_pct_mult,
                 salary_eff_mult, raw_score, price, market_cap, prev_price, change_pct)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (player_season_id, trade_date) DO UPDATE SET
                perf_score = EXCLUDED.perf_score, age_mult = EXCLUDED.age_mult,
                win_pct_mult = EXCLUDED.win_pct_mult, salary_eff_mult = EXCLUDED.salary_eff_mult,
                raw_score = EXCLUDED.raw_score, price = EXCLUDED.price,
                market_cap = EXCLUDED.market_cap, prev_price = EXCLUDED.prev_price,
                change_pct = EXCLUDED.change_pct
            """,
            (player_season_id, trade_date, perf_score, age_mult, win_pct_mult,
             salary_eff_mult, raw_score, price, market_cap, prev_price, change_pct),
        )
