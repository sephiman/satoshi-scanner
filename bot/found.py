"""Durable on-disk record of found wallets, written before any alerting.

A hit is the one event this service exists for; if the Telegram alert fails,
the key must still survive somewhere more durable than container logs.
"""
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import config
from checker import Hit
from metrics import FOUND_PERSIST_ERRORS_TOTAL

log = logging.getLogger(__name__)


def record(hit: Hit) -> None:
    """Append the hit to FOUND_WALLETS_FILE as one JSON line. Never raises:
    killing the scanner over a disk error would also forfeit future hits."""
    try:
        path = Path(config.FOUND_WALLETS_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "found_at": datetime.now(UTC).isoformat(),
            "address": hit.address,
            "address_type": hit.addr_type,
            "balance_btc": hit.balance,
            "private_key": hit.wallet.priv_hex,
            "public_key_compressed": hit.wallet.pub_compressed_hex,
            "public_key_uncompressed": hit.wallet.pub_uncompressed_hex,
        }
        with path.open("a", encoding="ascii") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        FOUND_PERSIST_ERRORS_TOTAL.inc()
        log.exception(
            "Could not persist found wallet %s to %s", hit.address, config.FOUND_WALLETS_FILE
        )
