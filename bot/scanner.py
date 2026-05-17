import logging
import time

import requests

from metrics import (
    BLOCKSTREAM_BACKOFF_SECONDS,
    BLOCKSTREAM_COOLDOWN_ACTIVE,
    BLOCKSTREAM_REQUESTS_TOTAL,
    time_blockstream_call,
)

log = logging.getLogger(__name__)

_session = requests.Session()
_session.headers.update({"User-Agent": "satoshi-scanner"})

# Cooldown until which we skip API calls (set when we hit 429).
_cooldown_until = 0.0
_INITIAL_BACKOFF = 5.0
_MAX_BACKOFF = 300.0
_backoff = _INITIAL_BACKOFF
BLOCKSTREAM_BACKOFF_SECONDS.set(_backoff)
BLOCKSTREAM_COOLDOWN_ACTIVE.set(0)


def check_balance_blockstream(addr):
    global _cooldown_until, _backoff

    now = time.monotonic()
    if now < _cooldown_until:
        BLOCKSTREAM_REQUESTS_TOTAL.labels(outcome="skipped_cooldown").inc()
        return 0.0
    BLOCKSTREAM_COOLDOWN_ACTIVE.set(0)

    try:
        with time_blockstream_call():
            r = _session.get(
                f"https://blockstream.info/api/address/{addr}", timeout=10
            )
        if r.status_code == 429:
            _cooldown_until = now + _backoff
            log.info("Rate limited; cooling down for %.0fs", _backoff)
            BLOCKSTREAM_REQUESTS_TOTAL.labels(outcome="rate_limited").inc()
            BLOCKSTREAM_COOLDOWN_ACTIVE.set(1)
            _backoff = min(_backoff * 2, _MAX_BACKOFF)
            BLOCKSTREAM_BACKOFF_SECONDS.set(_backoff)
            return 0.0

        r.raise_for_status()
        _backoff = _INITIAL_BACKOFF  # success resets backoff
        BLOCKSTREAM_BACKOFF_SECONDS.set(_backoff)
        BLOCKSTREAM_REQUESTS_TOTAL.labels(outcome="success").inc()
        data = r.json()
        funded = data.get("chain_stats", {}).get("funded_txo_sum", 0)
        spent = data.get("chain_stats", {}).get("spent_txo_sum", 0)
        return (funded - spent) / 100_000_000
    except requests.HTTPError as e:
        log.warning("Balance lookup HTTP error for %s: %s", addr, e)
        BLOCKSTREAM_REQUESTS_TOTAL.labels(outcome="http_error").inc()
        return 0.0
    except requests.RequestException as e:
        log.warning("Balance lookup failed for %s: %s", addr, e)
        BLOCKSTREAM_REQUESTS_TOTAL.labels(outcome="network_error").inc()
        return 0.0
