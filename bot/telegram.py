import logging
import time

import requests

import config
from metrics import TELEGRAM_SEND_ERRORS_TOTAL, TELEGRAM_SENT_TOTAL

log = logging.getLogger(__name__)

_session = requests.Session()

_RETRY_BASE_DELAY = 1.0


def escape_markdown(text: str) -> str:
    """Escape Telegram MarkdownV2 special characters in a plain-text fragment."""
    for ch in "\\_*[]()~`>#+-=|{}.!":
        text = text.replace(ch, "\\" + ch)
    return text


def send_to_telegram(message: str, retries: int = 0) -> bool:
    """Send a MarkdownV2 message; retry with exponential backoff up to
    `retries` extra attempts. Returns True once the message is delivered."""
    if not config.TELEGRAM_TOKEN or not config.TELEGRAM_CHAT_ID:
        log.warning("TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not configured")
        return False

    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "MarkdownV2",
    }
    for attempt in range(retries + 1):
        try:
            r = _session.post(url, json=payload, timeout=10)
            r.raise_for_status()
            TELEGRAM_SENT_TOTAL.inc()
            return True
        except requests.RequestException as e:
            TELEGRAM_SEND_ERRORS_TOTAL.inc()
            if attempt < retries:
                delay = _RETRY_BASE_DELAY * 2**attempt
                log.warning(
                    "Telegram send failed (attempt %d/%d): %s — retrying in %.0fs",
                    attempt + 1, retries + 1, e, delay,
                )
                time.sleep(delay)
            else:
                log.warning("Telegram send failed after %d attempt(s): %s", retries + 1, e)
    return False
