"""Central runtime configuration, read from the environment once at import.

Every other module imports from here instead of calling os.getenv itself, so
there is a single place to see (and in tests, monkeypatch) the knobs.
"""
import os


def _get(name: str, default: str) -> str:
    # Treat empty strings as unset: compose env_file passes through blank
    # values like `FUNDED_ADDRESSES_URL=` verbatim.
    value = os.getenv(name)
    return value if value else default


CHECK_MODE = _get("CHECK_MODE", "live").lower()
SCAN_INTERVAL = float(_get("SCAN_INTERVAL", "1.0"))
METRICS_PORT = int(_get("METRICS_PORT", "8000"))
LOG_LEVEL = _get("LOG_LEVEL", "INFO")

# Keys generated per scan iteration in database mode (live mode always uses 1).
BATCH_SIZE = int(_get("BATCH_SIZE", "1000"))

# Address forms derived per private key; see generator.KNOWN_ADDRESS_TYPES.
ADDRESS_TYPES = tuple(
    t.strip()
    for t in _get("ADDRESS_TYPES", "p2pkh_c,p2pkh_u,p2sh_p2wpkh,p2wpkh,p2tr").split(",")
    if t.strip()
)

TELEGRAM_TOKEN = _get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = _get("TELEGRAM_CHAT_ID", "")

POSTGRES_HOST = _get("POSTGRES_HOST", "postgresdb")
POSTGRES_PORT = int(_get("POSTGRES_PORT", "5432"))
POSTGRES_USER = _get("POSTGRES_USER", "")
POSTGRES_PASSWORD = _get("POSTGRES_PASSWORD", "")
POSTGRES_DB = _get("POSTGRES_DB", "")

FUNDED_ADDRESSES_URL = _get(
    "FUNDED_ADDRESSES_URL", "http://addresses.loyce.club/Bitcoin_addresses_LATEST.txt.gz"
)

# Re-download the funded-address dump when it is older than this. 0 disables.
DUMP_MAX_AGE_DAYS = int(_get("DUMP_MAX_AGE_DAYS", "0"))

# Append-only JSONL record of found wallets, written before any alerting.
FOUND_WALLETS_FILE = _get("FOUND_WALLETS_FILE", "data/found_wallets.jsonl")
