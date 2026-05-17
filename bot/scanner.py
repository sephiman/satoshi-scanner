import logging
import time

import requests

log = logging.getLogger(__name__)

_session = requests.Session()
_session.headers.update({"User-Agent": "satoshi-scanner"})

# Cooldown until which we skip API calls (set when we hit 429).
_cooldown_until = 0.0
_INITIAL_BACKOFF = 5.0
_MAX_BACKOFF = 300.0
_backoff = _INITIAL_BACKOFF


def check_balance_blockstream(addr):
    global _cooldown_until, _backoff

    now = time.monotonic()
    if now < _cooldown_until:
        return 0.0

    try:
        r = _session.get(
            f"https://blockstream.info/api/address/{addr}", timeout=10
        )
        if r.status_code == 429:
            _cooldown_until = now + _backoff
            log.info("Rate limited; cooling down for %.0fs", _backoff)
            _backoff = min(_backoff * 2, _MAX_BACKOFF)
            return 0.0

        r.raise_for_status()
        _backoff = _INITIAL_BACKOFF  # success resets backoff
        data = r.json()
        funded = data.get("chain_stats", {}).get("funded_txo_sum", 0)
        spent = data.get("chain_stats", {}).get("spent_txo_sum", 0)
        return (funded - spent) / 100_000_000
    except requests.RequestException as e:
        log.warning("Balance lookup failed for %s: %s", addr, e)
        return 0.0
