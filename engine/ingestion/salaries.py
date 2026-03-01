import logging

import numpy as np
from basketball_reference_web_scraper import client as br_client

import db

log = logging.getLogger(__name__)


def _season_end_year(season_year: int) -> int:
    """basketball_reference_web_scraper expects the end year (e.g. 2026 for 2025-26)."""
    return season_year + 1


def sync_salaries(conn, season_year: int):
    """
    Fetch salaries from Basketball Reference and upsert into player_salaries.
    season_year is the starting year (e.g. 2025 for the 2025-26 season).
    """
    season_label = f"{season_year}-{str(season_year + 1)[-2:]}"
    log.info("Syncing salaries for season %s", season_label)

    season = db.get_season_by_label(conn, season_label)
    if not season:
        log.error("Season %s not found in database", season_label)
        return

    end_year = _season_end_year(season_year)
    try:
        salaries = br_client.players_season_totals(season_end_year=end_year)
    except Exception:
        log.exception("Failed to fetch salaries from Basketball Reference")
        return

    salary_rows = []
    for entry in salaries:
        name = entry.get("name", "")
        salary = entry.get("salary", None)
        if not name or salary is None:
            continue

        parts = name.split(" ", 1)
        first_name = parts[0] if len(parts) > 0 else ""
        last_name = parts[1] if len(parts) > 1 else ""

        player = db.get_player_by_name(conn, first_name, last_name)
        if not player:
            log.debug("Player not found in DB: %s", name)
            continue

        salary_rows.append({"player_id": player["id"], "salary": int(salary)})

    if not salary_rows:
        log.warning("No salary data matched to players")
        return

    all_salaries = np.array([r["salary"] for r in salary_rows], dtype=float)

    for row in salary_rows:
        pct = float(np.sum(all_salaries <= row["salary"]) / len(all_salaries) * 100)
        db.upsert_player_salary(conn, player_id=row["player_id"], season_id=season["id"],
                                salary=row["salary"], percentile=pct)

    conn.commit()
    log.info("Synced salaries for %d players", len(salary_rows))
