import logging
import os

import requests

from metrics import TELEGRAM_SEND_ERRORS_TOTAL, TELEGRAM_SENT_TOTAL

log = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

_session = requests.Session()


def send_to_telegram(message: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not configured")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
    }
    try:
        r = _session.post(url, json=payload, timeout=10)
        r.raise_for_status()
        TELEGRAM_SENT_TOTAL.inc()
    except Exception as e:
        log.warning("Telegram send failed: %s", e)
        TELEGRAM_SEND_ERRORS_TOTAL.inc()
