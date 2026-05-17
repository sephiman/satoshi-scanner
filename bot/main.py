import logging
import os
import time

from generator import generate_random_wallet
from scanner import check_balance_blockstream
from telegram import send_to_telegram

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("scanner")

SCAN_INTERVAL = float(os.getenv("SCAN_INTERVAL", "1.0"))


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
    send_to_telegram("*Satoshi Scanner Started*")

    while True:
        priv, pub, addr = generate_random_wallet()
        balance = check_balance_blockstream(addr)
        log.debug("Scanned %s balance=%s BTC", addr, balance)

        if balance > 0:
            log.info("Wallet with balance found: %s (%s BTC)", addr, balance)
            send_to_telegram(format_alert("*Wallet Found!*", addr, balance, pub, priv))

        if SCAN_INTERVAL > 0:
            time.sleep(SCAN_INTERVAL)


if __name__ == "__main__":
    main()
