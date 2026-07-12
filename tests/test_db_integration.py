import gzip
import io
from datetime import UTC, datetime

import pytest
import responses

import db
from metrics import DB_FUNDED_ADDRESSES_ROWS

pytestmark = pytest.mark.integration

DUMP_URL = "http://fake-dump.test/addresses.txt.gz"


def _gzip_bytes(addresses):
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
        gz.write(("\n".join(addresses) + "\n").encode("ascii"))
    return buf.getvalue()


def _add_dump(addresses):
    responses.add(
        responses.GET, DUMP_URL, body=_gzip_bytes(addresses), content_type="application/gzip"
    )


def test_ensure_schema_creates_tables(db_conn):
    db.ensure_schema(db_conn)

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_name IN ('funded_addresses', 'scanner_meta')"
        )
        assert {row[0] for row in cur.fetchall()} == {"funded_addresses", "scanner_meta"}


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


def test_addresses_with_funds_batch(db_conn):
    db.ensure_schema(db_conn)
    with db_conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO funded_addresses VALUES (%s)", [("1known",), ("bc1qknown",)]
        )
    db_conn.commit()

    result = db.addresses_with_funds(
        db_conn, ["1known", "bc1qknown", "1unknown", "3unknown"]
    )
    assert result == {"1known", "bc1qknown"}

    assert db.addresses_with_funds(db_conn, []) == set()
    assert db.addresses_with_funds(db_conn, ["1unknown"]) == set()


def test_meta_roundtrip(db_conn):
    db.ensure_schema(db_conn)

    assert db.get_meta(db_conn, "some_key") is None
    db.set_meta(db_conn, "some_key", "v1")
    assert db.get_meta(db_conn, "some_key") == "v1"
    db.set_meta(db_conn, "some_key", "v2")  # upsert
    assert db.get_meta(db_conn, "some_key") == "v2"


@responses.activate
def test_populate_from_dump_loads_addresses_and_marks_time(db_conn):
    _add_dump(["1addr_one", "1addr_two", "1addr_three"])
    db.ensure_schema(db_conn)

    before = datetime.now(UTC)
    count = db.populate_from_dump(db_conn, url=DUMP_URL)

    assert count == 3
    assert db.addresses_with_funds(db_conn, ["1addr_one", "1addr_missing"]) == {"1addr_one"}

    loaded_at = db.dump_loaded_at(db_conn)
    assert loaded_at is not None
    assert loaded_at >= before


@responses.activate
def test_populate_from_dump_skips_blank_lines(db_conn):
    _add_dump(["1one", "", "1two", "   ", "1three"])
    db.ensure_schema(db_conn)

    assert db.populate_from_dump(db_conn, url=DUMP_URL) == 3


@responses.activate
def test_refresh_dataset_swaps_atomically(db_conn):
    db.ensure_schema(db_conn)
    _add_dump(["1old_a", "1old_b"])
    db.populate_from_dump(db_conn, url=DUMP_URL)

    _add_dump(["1new_a", "1new_b", "1new_c"])
    count = db.refresh_dataset(db_conn, url=DUMP_URL)

    assert count == 3
    assert db.addresses_with_funds(db_conn, ["1old_a", "1old_b"]) == set()
    assert db.addresses_with_funds(db_conn, ["1new_a", "1new_b", "1new_c"]) == {
        "1new_a", "1new_b", "1new_c",
    }

    # A second refresh must not trip over leftover staging index names.
    _add_dump(["1newer_a"])
    assert db.refresh_dataset(db_conn, url=DUMP_URL) == 1
    assert db.addresses_with_funds(db_conn, ["1newer_a"]) == {"1newer_a"}


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
