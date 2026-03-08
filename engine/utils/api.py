"""API helpers: rate limiting, retries for nba_api."""

import logging
import os
import time

from constants import REQUEST_DELAY

log = logging.getLogger(__name__)

# Max retries for transient failures (timeouts, connection errors)
MAX_RETRIES = 4
RETRY_BACKOFF = 3  # seconds, doubles each attempt
# Longer timeout for GitHub Actions / cloud runners
REQUEST_TIMEOUT = 120

# Optional proxy to bypass NBA.com's IP block on datacenter IPs (GitHub Actions, Heroku, etc.)
# Format: "http://user:pass@host:port" or "http://host:port"
# See DEPLOYMENT.md for details.
NBA_API_PROXY = os.environ.get("NBA_API_PROXY", "").strip() or None


def safe_request(endpoint_cls, **kwargs):
    """Call nba_api endpoint with delay and retries on failure (timeouts, connection errors)."""
    time.sleep(REQUEST_DELAY)
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    if NBA_API_PROXY:
        kwargs.setdefault("proxy", NBA_API_PROXY)
    endpoint_name = endpoint_cls.__name__
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            t0 = time.time()
            log.info("[NBA API] %s (attempt %d/%d) starting...", endpoint_name, attempt + 1, MAX_RETRIES)
            result = endpoint_cls(**kwargs)
            elapsed = time.time() - t0
            log.info("[NBA API] %s succeeded in %.1fs", endpoint_name, elapsed)
            return result
        except Exception as e:
            elapsed = time.time() - t0
            last_err = e
            log.warning(
                "[NBA API] %s failed after %.1fs (attempt %d/%d): %s",
                endpoint_name, elapsed, attempt + 1, MAX_RETRIES, e,
            )
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF * (2 ** attempt)
                log.info("[NBA API] Retrying in %ds...", wait)
                time.sleep(wait)
            else:
                log.error("[NBA API] %s failed after %d attempts", endpoint_name, MAX_RETRIES)
                raise last_err
