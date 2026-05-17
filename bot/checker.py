import logging
import os

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
    return _conn


def check_address(addr):
    if CHECK_MODE == "database":
        import db
        conn = _db_conn()
        if not db.address_has_funds(conn, addr):
            return 0.0
        log.info("Database HIT for %s — verifying against Blockstream", addr)
        return check_balance_blockstream(addr)

    return check_balance_blockstream(addr)


def init():
    log.info("Check mode: %s", CHECK_MODE)
    if CHECK_MODE == "database":
        _db_conn()
