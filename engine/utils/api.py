"""API helpers: rate limiting, retries for nba_api."""

import logging
import time

from constants import REQUEST_DELAY

log = logging.getLogger(__name__)

# Max retries for transient failures (timeouts, connection errors)
MAX_RETRIES = 4
RETRY_BACKOFF = 3  # seconds, doubles each attempt
# Longer timeout for GitHub Actions / cloud runners (NBA API is slow from datacenter IPs)
REQUEST_TIMEOUT = 90


def safe_request(endpoint_cls, **kwargs):
    """Call nba_api endpoint with delay and retries on failure (timeouts, connection errors)."""
    time.sleep(REQUEST_DELAY)
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            return endpoint_cls(**kwargs)
        except Exception as e:
            last_err = e
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF * (2 ** attempt)
                log.warning("API request failed (attempt %d/%d): %s — retrying in %ds", attempt + 1, MAX_RETRIES, e, wait)
                time.sleep(wait)
            else:
                log.error("API request failed after %d attempts: %s", MAX_RETRIES, e)
                raise last_err
