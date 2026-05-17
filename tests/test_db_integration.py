import gzip
import io

import pytest
import responses

import db
from metrics import DB_FUNDED_ADDRESSES_ROWS

pytestmark = pytest.mark.integration


def _gzip_bytes(addresses):
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
        gz.write(("\n".join(addresses) + "\n").encode("ascii"))
    return buf.getvalue()


def test_ensure_schema_creates_table(db_conn):
    db.ensure_schema(db_conn)

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name = 'funded_addresses'"
        )
        assert cur.fetchone() is not None


def test_ensure_schema_is_idempotent(db_conn):
    db.ensure_schema(db_conn)
    db.ensure_schema(db_conn)

    with db_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM funded_addresses")
        assert cur.fetchone()[0] == 0


def test_is_table_empty(db_conn):
    db.ensure_schema(db_conn)
    assert db.is_table_empty(db_conn) is True

    with db_conn.cursor() as cur:
        cur.execute("INSERT INTO funded_addresses VALUES ('1abc')")
    db_conn.commit()

    assert db.is_table_empty(db_conn) is False


def test_address_has_funds(db_conn):
    db.ensure_schema(db_conn)
    with db_conn.cursor() as cur:
        cur.execute("INSERT INTO funded_addresses VALUES ('1known')")
    db_conn.commit()

    assert db.address_has_funds(db_conn, "1known") is True
    assert db.address_has_funds(db_conn, "1unknown") is False


@responses.activate
def test_populate_from_dump_loads_addresses(db_conn):
    addresses = ["1addr_one", "1addr_two", "1addr_three"]
    url = "http://fake-dump.test/addresses.txt.gz"

    responses.add(
        responses.GET,
        url,
        body=_gzip_bytes(addresses),
        content_type="application/gzip",
    )

    db.ensure_schema(db_conn)
    count = db.populate_from_dump(db_conn, url=url)

    assert count == 3
    assert db.address_has_funds(db_conn, "1addr_one")
    assert db.address_has_funds(db_conn, "1addr_two")
    assert db.address_has_funds(db_conn, "1addr_three")
    assert not db.address_has_funds(db_conn, "1addr_missing")


@responses.activate
def test_populate_from_dump_skips_blank_lines(db_conn):
    url = "http://fake-dump.test/addresses.txt.gz"

    responses.add(
        responses.GET,
        url,
        body=_gzip_bytes(["1one", "", "1two", "   ", "1three"]),
        content_type="application/gzip",
    )

    db.ensure_schema(db_conn)
    count = db.populate_from_dump(db_conn, url=url)

    assert count == 3


def test_refresh_row_count_updates_gauge(db_conn):
    db.ensure_schema(db_conn)
    with db_conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO funded_addresses VALUES (%s)",
            [("1a",), ("1b",), ("1c",)],
        )
    db_conn.commit()

    with db_conn.cursor() as cur:
        cur.execute("ANALYZE funded_addresses")
    db_conn.commit()

    DB_FUNDED_ADDRESSES_ROWS.set(0)
    db.refresh_row_count(db_conn)

    assert DB_FUNDED_ADDRESSES_ROWS._value.get() == 3
