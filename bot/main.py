import logging
import os
import time

from prometheus_client import start_http_server

import checker
from generator import generate_random_wallet
from metrics import (
    ADDRESSES_CHECKED_TOTAL,
    ADDRESSES_GENERATED_TOTAL,
    LAST_CHECK_TIMESTAMP,
    WALLETS_FOUND_TOTAL,
)
from telegram import send_to_telegram

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("scanner")

SCAN_INTERVAL = float(os.getenv("SCAN_INTERVAL", "1.0"))
METRICS_PORT = int(os.getenv("METRICS_PORT", "8000"))
CHECK_MODE = os.getenv("CHECK_MODE", "live").lower()


def format_alert(title, addr, balance, pub, priv):
    return (
        f"{title}\n"
        f"*Address:* `{addr}`\n"
        f"[View on Blockstream](https://blockstream.info/address/{addr})\n"
        f"*Balance:* `{balance} BTC`\n"
        f"*Public Key:* `{pub}`\n"
        f"*Private Key:* `{priv}`"
    )


def main():
    log.info("Starting BTC address scanner (interval=%ss)", SCAN_INTERVAL)
    start_http_server(METRICS_PORT)
    log.info("Prometheus metrics exposed on :%d/metrics", METRICS_PORT)
    checker.init()
    send_to_telegram("*Satoshi Scanner Started*")

    while True:
        priv, pub, addr = generate_random_wallet()
        ADDRESSES_GENERATED_TOTAL.inc()
        balance = checker.check_address(addr)
        LAST_CHECK_TIMESTAMP.set_to_current_time()
        log.debug("Scanned %s balance=%s BTC", addr, balance)

        if balance > 0:
            ADDRESSES_CHECKED_TOTAL.labels(mode=CHECK_MODE, result="hit").inc()
            WALLETS_FOUND_TOTAL.inc()
            log.info("Wallet with balance found: %s (%s BTC)", addr, balance)
            send_to_telegram(format_alert("*Wallet Found!*", addr, balance, pub, priv))
        else:
            ADDRESSES_CHECKED_TOTAL.labels(mode=CHECK_MODE, result="zero").inc()

        if SCAN_INTERVAL > 0:
            time.sleep(SCAN_INTERVAL)


if __name__ == "__main__":
    main()
