import logging
import os

from metrics import DB_LOOKUPS_TOTAL, time_db_lookup
from scanner import check_balance_blockstream

log = logging.getLogger(__name__)

CHECK_MODE = os.getenv("CHECK_MODE", "live").lower()

_conn = None


def _db_conn():
    global _conn
    if _conn is None:
        import db
        _conn = db.get_conn()
        db.ensure_schema(_conn)
        if db.is_table_empty(_conn):
            db.populate_from_dump(_conn)
        else:
            log.info("funded_addresses already populated; skipping dump load")
        db.refresh_row_count(_conn)
    return _conn


def _reset_conn():
    """Drop the cached connection so the next lookup reconnects. Called when a
    DB error suggests the connection is broken (e.g. Postgres restarted)."""
    global _conn
    if _conn is not None:
        try:
            _conn.close()
        except Exception:
            pass
        _conn = None


def _check_database(addr):
    import psycopg

    import db

    try:
        conn = _db_conn()
        with time_db_lookup():
            has_funds = db.address_has_funds(conn, addr)
    except psycopg.Error:
        _reset_conn()
        raise

    if not has_funds:
        DB_LOOKUPS_TOTAL.labels(result="miss").inc()
        return 0.0
    DB_LOOKUPS_TOTAL.labels(result="hit").inc()
    log.info("Database HIT for %s — verifying against Blockstream", addr)
    return check_balance_blockstream(addr)


def check_address(addr):
    if CHECK_MODE == "database":
        return _check_database(addr)
    return check_balance_blockstream(addr)


def init():
    log.info("Check mode: %s", CHECK_MODE)
    if CHECK_MODE == "database":
        _db_conn()
