import gzip
import logging
import os

import psycopg
import requests

log = logging.getLogger(__name__)

FUNDED_ADDRESSES_URL = os.getenv(
    "FUNDED_ADDRESSES_URL",
    "http://addresses.loyce.club/Bitcoin_addresses_LATEST.txt.gz",
)
DUMP_REQUEST_TIMEOUT = 60
PROGRESS_EVERY = 1_000_000


def get_conn():
    return psycopg.connect(
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        dbname=os.environ["POSTGRES_DB"],
        autocommit=False,
    )


def ensure_schema(conn):
    with conn.cursor() as cur:
        cur.execute(
            "CREATE TABLE IF NOT EXISTS funded_addresses (address TEXT PRIMARY KEY)"
        )
    conn.commit()


def is_table_empty(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM funded_addresses LIMIT 1")
        return cur.fetchone() is None


def populate_from_dump(conn, url=FUNDED_ADDRESSES_URL):
    log.info("funded_addresses is empty; downloading dump from %s", url)

    with requests.get(url, stream=True, timeout=DUMP_REQUEST_TIMEOUT) as r:
        r.raise_for_status()
        with gzip.GzipFile(fileobj=r.raw) as gz, conn.cursor() as cur:
            count = 0
            with cur.copy("COPY funded_addresses (address) FROM STDIN") as copy:
                for raw in gz:
                    addr = raw.strip()
                    if not addr:
                        continue
                    copy.write_row((addr.decode("ascii"),))
                    count += 1
                    if count % PROGRESS_EVERY == 0:
                        log.info("Loaded %d addresses…", count)
        conn.commit()

    log.info("Funded-address dump loaded: %d addresses", count)
    return count


def address_has_funds(conn, addr):
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM funded_addresses WHERE address = %s", (addr,))
        return cur.fetchone() is not None
