import logging
import signal
import threading
from types import FrameType

from prometheus_client import start_http_server

import checker
import config
import found
from checker import Hit
from generator import generate_wallet, validate_address_types
from metrics import (
    ADDRESSES_CHECKED_TOTAL,
    ADDRESSES_GENERATED_TOTAL,
    KEYS_GENERATED_TOTAL,
    LAST_CHECK_TIMESTAMP,
    SCAN_ERRORS_TOTAL,
    WALLETS_FOUND_TOTAL,
)
from telegram import send_to_telegram

logging.basicConfig(
    level=config.LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("scanner")

# Extra send attempts for the one alert that matters.
ALERT_RETRIES = 5

# Set when a shutdown signal is received. Used both to break the scan loop and
# as an interruptible replacement for time.sleep so shutdown is prompt.
_shutdown = threading.Event()


def _handle_signal(signum: int, _frame: FrameType | None) -> None:
    log.info("Received %s; shutting down gracefully", signal.Signals(signum).name)
    _shutdown.set()


def format_alert(hit: Hit) -> str:
    return (
        "*Wallet Found\\!*\n"
        f"*Address:* `{hit.address}`\n"
        f"*Type:* `{hit.addr_type}`\n"
        f"[View on Blockstream](https://blockstream.info/address/{hit.address})\n"
        f"*Balance:* `{hit.balance} BTC`\n"
        f"*Private Key:* `{hit.wallet.priv_hex}`\n"
        f"*Public Key:* `{hit.wallet.pub_compressed_hex}`"
    )


def scan_once() -> None:
    batch_size = config.BATCH_SIZE if config.CHECK_MODE == "database" else 1
    wallets = [generate_wallet() for _ in range(batch_size)]
    KEYS_GENERATED_TOTAL.inc(len(wallets))
    n_addresses = sum(len(w.addresses) for w in wallets)
    ADDRESSES_GENERATED_TOTAL.inc(n_addresses)

    hits = checker.check_batch(wallets)
    LAST_CHECK_TIMESTAMP.set_to_current_time()
    ADDRESSES_CHECKED_TOTAL.labels(mode=config.CHECK_MODE, result="hit").inc(len(hits))
    ADDRESSES_CHECKED_TOTAL.labels(mode=config.CHECK_MODE, result="zero").inc(
        n_addresses - len(hits)
    )

    for hit in hits:
        WALLETS_FOUND_TOTAL.inc()
        log.info(
            "Wallet with balance found: %s (%s, %s BTC)", hit.address, hit.addr_type, hit.balance
        )
        found.record(hit)  # durable first — the alert may fail
        send_to_telegram(format_alert(hit), retries=ALERT_RETRIES)


def main() -> None:
    log.info(
        "Starting BTC address scanner (mode=%s, interval=%ss, address types: %s)",
        config.CHECK_MODE, config.SCAN_INTERVAL, ", ".join(config.ADDRESS_TYPES),
    )
    validate_address_types(config.ADDRESS_TYPES)
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    start_http_server(config.METRICS_PORT)
    log.info("Prometheus metrics exposed on :%d/metrics", config.METRICS_PORT)
    checker.init()
    send_to_telegram("*Satoshi Scanner Started*")

    try:
        while not _shutdown.is_set():
            try:
                checker.maybe_refresh_dataset()
                scan_once()
            except Exception:
                # A single failed iteration (network blip, dropped DB
                # connection, …) must not take the scanner down; checker
                # rebuilds a broken DB connection on the next pass.
                SCAN_ERRORS_TOTAL.inc()
                log.exception("Scan iteration failed; continuing")

            if config.SCAN_INTERVAL > 0:
                _shutdown.wait(config.SCAN_INTERVAL)
    finally:
        checker.close()

    log.info("Scanner stopped")


if __name__ == "__main__":
    main()
