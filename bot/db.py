import gzip
import logging
from datetime import UTC, datetime

import psycopg
import requests

import config
from metrics import DB_FUNDED_ADDRESSES_ROWS, DUMP_LOADED_TIMESTAMP

log = logging.getLogger(__name__)

DUMP_REQUEST_TIMEOUT = 60
PROGRESS_EVERY = 1_000_000

_META_DUMP_LOADED_AT = "dump_loaded_at"


def get_conn() -> psycopg.Connection:
    return psycopg.connect(
        host=config.POSTGRES_HOST,
        port=config.POSTGRES_PORT,
        user=config.POSTGRES_USER,
        password=config.POSTGRES_PASSWORD,
        dbname=config.POSTGRES_DB,
        autocommit=False,
    )


def ensure_schema(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "CREATE TABLE IF NOT EXISTS funded_addresses (address TEXT PRIMARY KEY)"
        )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS scanner_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
    conn.commit()


def is_table_empty(conn: psycopg.Connection) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM funded_addresses LIMIT 1")
        return cur.fetchone() is None


def get_meta(conn: psycopg.Connection, key: str) -> str | None:
    with conn.cursor() as cur:
        cur.execute("SELECT value FROM scanner_meta WHERE key = %s", (key,))
        row = cur.fetchone()
        return row[0] if row else None


def set_meta(conn: psycopg.Connection, key: str, value: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO scanner_meta (key, value) VALUES (%s, %s) "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
            (key, value),
        )
    conn.commit()


def dump_loaded_at(conn: psycopg.Connection) -> datetime | None:
    raw = get_meta(conn, _META_DUMP_LOADED_AT)
    return datetime.fromisoformat(raw) if raw else None


def mark_dump_loaded(conn: psycopg.Connection, when: datetime | None = None) -> None:
    when = when or datetime.now(UTC)
    set_meta(conn, _META_DUMP_LOADED_AT, when.isoformat())
    DUMP_LOADED_TIMESTAMP.set(when.timestamp())


def _copy_dump_into(conn: psycopg.Connection, table: str, url: str) -> int:
    log.info("Downloading funded-address dump from %s into %s", url, table)
    with requests.get(url, stream=True, timeout=DUMP_REQUEST_TIMEOUT) as r:
        r.raise_for_status()
        with gzip.GzipFile(fileobj=r.raw) as gz, conn.cursor() as cur:
            count = 0
            with cur.copy(f"COPY {table} (address) FROM STDIN") as copy:
                for raw in gz:
                    addr = raw.strip()
                    if not addr:
                        continue
                    copy.write_row((addr.decode("ascii"),))
                    count += 1
                    if count % PROGRESS_EVERY == 0:
                        log.info("Loaded %d addresses…", count)
    log.info("Funded-address dump loaded into %s: %d addresses", table, count)
    return count


def populate_from_dump(conn: psycopg.Connection, url: str | None = None) -> int:
    count = _copy_dump_into(conn, "funded_addresses", url or config.FUNDED_ADDRESSES_URL)
    conn.commit()
    mark_dump_loaded(conn)
    DB_FUNDED_ADDRESSES_ROWS.set(count)
    return count


def refresh_dataset(conn: psycopg.Connection, url: str | None = None) -> int:
    """Reload the dump into a staging table, then atomically swap it in, so
    lookups keep hitting the old data until the new set is fully loaded."""
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS funded_addresses_staging")
        cur.execute("CREATE TABLE funded_addresses_staging (address TEXT PRIMARY KEY)")
    count = _copy_dump_into(conn, "funded_addresses_staging", url or config.FUNDED_ADDRESSES_URL)
    with conn.cursor() as cur:
        cur.execute("DROP TABLE funded_addresses")
        cur.execute("ALTER TABLE funded_addresses_staging RENAME TO funded_addresses")
        # Rename the PK index too, or the next refresh's staging table would
        # collide with the leftover funded_addresses_staging_pkey name.
        cur.execute("ALTER INDEX funded_addresses_staging_pkey RENAME TO funded_addresses_pkey")
    conn.commit()
    mark_dump_loaded(conn)
    DB_FUNDED_ADDRESSES_ROWS.set(count)
    return count


def addresses_with_funds(conn: psycopg.Connection, addrs: list[str]) -> set[str]:
    """Return the subset of addrs present in funded_addresses (one query)."""
    if not addrs:
        return set()
    with conn.cursor() as cur:
        cur.execute("SELECT address FROM funded_addresses WHERE address = ANY(%s)", (addrs,))
        return {row[0] for row in cur.fetchall()}


def refresh_row_count(conn: psycopg.Connection) -> None:
    """Update the funded_addresses_rows gauge. Uses pg_class.reltuples (an
    estimate) — fast even on huge tables, no full scan needed."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT reltuples::BIGINT FROM pg_class WHERE relname = 'funded_addresses'"
            )
            row = cur.fetchone()
            if row and row[0] is not None:
                DB_FUNDED_ADDRESSES_ROWS.set(int(row[0]))
    except psycopg.Error as e:
        log.warning("Could not refresh funded_addresses row-count gauge: %s", e)
