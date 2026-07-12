import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import psycopg

import config
import db
from generator import Wallet
from metrics import DB_LOOKUPS_TOTAL, time_db_lookup
from scanner import check_balance_blockstream

log = logging.getLogger(__name__)

_conn: psycopg.Connection | None = None
_dump_loaded_at: datetime | None = None


@dataclass(frozen=True)
class Hit:
    wallet: Wallet
    address: str
    addr_type: str
    balance: float


def _db_conn() -> psycopg.Connection:
    global _conn, _dump_loaded_at
    if _conn is None:
        _conn = db.get_conn()
        db.ensure_schema(_conn)
        if db.is_table_empty(_conn):
            db.populate_from_dump(_conn)
        else:
            log.info("funded_addresses already populated; skipping dump load")
            if db.dump_loaded_at(_conn) is None:
                # Dataset predates load-time tracking: stamp it now rather
                # than forcing an immediate re-download.
                db.mark_dump_loaded(_conn)
        _dump_loaded_at = db.dump_loaded_at(_conn)
        db.refresh_row_count(_conn)
    return _conn


def _reset_conn() -> None:
    """Drop the cached connection so the next lookup reconnects. Called when a
    DB error suggests the connection is broken (e.g. Postgres restarted)."""
    global _conn
    if _conn is not None:
        try:
            _conn.close()
        except Exception:
            pass
        _conn = None


def maybe_refresh_dataset() -> None:
    """Re-download the funded-address dump once it is older than
    DUMP_MAX_AGE_DAYS (database mode only; 0 disables)."""
    global _dump_loaded_at
    if config.CHECK_MODE != "database" or config.DUMP_MAX_AGE_DAYS <= 0:
        return
    if _dump_loaded_at is None:
        return
    age = datetime.now(UTC) - _dump_loaded_at
    if age < timedelta(days=config.DUMP_MAX_AGE_DAYS):
        return
    log.info("Funded-address dump is %s old; refreshing", age)
    try:
        db.refresh_dataset(_db_conn())
    except psycopg.Error:
        _reset_conn()
        raise
    _dump_loaded_at = datetime.now(UTC)


def _check_batch_live(wallets: list[Wallet]) -> list[Hit]:
    hits = []
    for wallet in wallets:
        for addr_type, addr in wallet.addresses.items():
            balance = check_balance_blockstream(addr)
            if balance > 0:
                hits.append(Hit(wallet, addr, addr_type, balance))
    return hits


def _check_batch_database(wallets: list[Wallet]) -> list[Hit]:
    by_addr = {
        addr: (wallet, addr_type)
        for wallet in wallets
        for addr_type, addr in wallet.addresses.items()
    }
    try:
        conn = _db_conn()
        with time_db_lookup():
            funded = db.addresses_with_funds(conn, list(by_addr))
    except psycopg.Error:
        _reset_conn()
        raise

    DB_LOOKUPS_TOTAL.labels(result="miss").inc(len(by_addr) - len(funded))
    DB_LOOKUPS_TOTAL.labels(result="hit").inc(len(funded))

    hits = []
    for addr in sorted(funded):
        log.info("Database HIT for %s — verifying against Blockstream", addr)
        wallet, addr_type = by_addr[addr]
        balance = check_balance_blockstream(addr)
        if balance > 0:
            hits.append(Hit(wallet, addr, addr_type, balance))
    return hits


def check_batch(wallets: list[Wallet]) -> list[Hit]:
    """Check every address of every wallet; return only funded ones."""
    if config.CHECK_MODE == "database":
        return _check_batch_database(wallets)
    return _check_batch_live(wallets)


def init() -> None:
    log.info("Check mode: %s", config.CHECK_MODE)
    if config.CHECK_MODE == "database":
        _db_conn()


def close() -> None:
    _reset_conn()
