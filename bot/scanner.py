import logging

import requests

log = logging.getLogger(__name__)

_session = requests.Session()


def check_balance_blockstream(addr):
    try:
        r = _session.get(f"https://blockstream.info/api/address/{addr}", timeout=10)
        r.raise_for_status()
        data = r.json()
        funded = data.get("chain_stats", {}).get("funded_txo_sum", 0)
        spent = data.get("chain_stats", {}).get("spent_txo_sum", 0)
        return (funded - spent) / 100_000_000
    except Exception as e:
        log.warning("Balance lookup failed for %s: %s", addr, e)
        return 0.0
