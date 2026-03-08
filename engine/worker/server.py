"""
Fly.io worker: HTTP endpoint to trigger daily market update.
Trigger via cron-job.org or similar. Protected by CRON_SECRET.
"""
import logging
import os
import subprocess
import sys
from pathlib import Path

from flask import Flask, request

app = Flask(__name__)
CRON_SECRET = os.environ.get("CRON_SECRET", "").strip()
ENGINE_DIR = Path(__file__).resolve().parent.parent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("worker")


def _check_auth() -> bool:
    if not CRON_SECRET:
        log.error("CRON_SECRET not set - refusing to run")
        return False
    token = request.args.get("token") or request.headers.get("Authorization", "").replace("Bearer ", "")
    return token == CRON_SECRET


@app.route("/run", methods=["GET", "POST"])
def run_update():
    """Run the daily market update. Requires ?token=CRON_SECRET or Authorization: Bearer CRON_SECRET."""
    if not _check_auth():
        return {"ok": False, "error": "unauthorized"}, 401

    season = request.args.get("season", "2025-26")
    log.info("Triggered market update for season %s", season)

    try:
        result = subprocess.run(
            [sys.executable, str(ENGINE_DIR / "scripts" / "update_market.py"), "--season", season],
            cwd=str(ENGINE_DIR),
            capture_output=True,
            text=True,
            timeout=600,  # 10 min max
            env={**os.environ},
        )
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        if result.returncode != 0:
            log.error("Update failed: %s\n%s", stderr, stdout)
            return {"ok": False, "error": stderr or "script failed", "stdout": stdout}, 500
        log.info("Update completed successfully")
        return {"ok": True, "stdout": stdout[-2000:] if len(stdout) > 2000 else stdout}
    except subprocess.TimeoutExpired:
        log.error("Update timed out after 10 minutes")
        return {"ok": False, "error": "timeout"}, 500
    except Exception as e:
        log.exception("Update failed")
        return {"ok": False, "error": str(e)}, 500


@app.route("/health")
def health():
    return {"ok": True}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
