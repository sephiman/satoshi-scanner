import psycopg
import pytest

import checker
import config
import db as db_module
from generator import Wallet


def make_wallet(n: int, addresses: dict[str, str]) -> Wallet:
    return Wallet(
        priv_hex=f"{n:064x}",
        pub_compressed_hex="02" + "ab" * 32,
        pub_uncompressed_hex="04" + "ab" * 64,
        addresses=addresses,
    )


@pytest.fixture(autouse=True)
def reset_checker_state():
    checker._conn = None
    checker._dump_loaded_at = None
    yield
    checker._conn = None
    checker._dump_loaded_at = None


def test_live_mode_checks_every_address(monkeypatch):
    monkeypatch.setattr(config, "CHECK_MODE", "live")
    wallet = make_wallet(1, {"p2pkh_c": "1abc", "p2wpkh": "bc1qabc"})

    calls = []
    monkeypatch.setattr(
        checker, "check_balance_blockstream", lambda addr: calls.append(addr) or 0.0
    )

    assert checker.check_batch([wallet]) == []
    assert calls == ["1abc", "bc1qabc"]


def test_live_mode_returns_hits(monkeypatch):
    monkeypatch.setattr(config, "CHECK_MODE", "live")
    wallet = make_wallet(1, {"p2pkh_c": "1abc", "p2wpkh": "bc1qabc"})

    monkeypatch.setattr(
        checker,
        "check_balance_blockstream",
        lambda addr: 0.42 if addr == "bc1qabc" else 0.0,
    )

    hits = checker.check_batch([wallet])
    assert len(hits) == 1
    assert hits[0].address == "bc1qabc"
    assert hits[0].addr_type == "p2wpkh"
    assert hits[0].balance == 0.42
    assert hits[0].wallet is wallet


def test_database_miss_skips_blockstream(monkeypatch):
    monkeypatch.setattr(config, "CHECK_MODE", "database")

    monkeypatch.setattr(checker, "_db_conn", lambda: object())
    monkeypatch.setattr(db_module, "addresses_with_funds", lambda conn, addrs: set())

    called = []
    monkeypatch.setattr(
        checker, "check_balance_blockstream", lambda addr: called.append(addr) or 1.0
    )

    wallets = [make_wallet(n, {"p2pkh_c": f"1abc{n}"}) for n in range(3)]
    assert checker.check_batch(wallets) == []
    assert called == []


def test_database_batches_all_addresses_in_one_lookup(monkeypatch):
    monkeypatch.setattr(config, "CHECK_MODE", "database")

    looked_up = []
    monkeypatch.setattr(checker, "_db_conn", lambda: object())
    monkeypatch.setattr(
        db_module,
        "addresses_with_funds",
        lambda conn, addrs: looked_up.append(sorted(addrs)) or set(),
    )
    monkeypatch.setattr(checker, "check_balance_blockstream", lambda addr: 0.0)

    wallets = [
        make_wallet(1, {"p2pkh_c": "1aaa", "p2wpkh": "bc1qaaa"}),
        make_wallet(2, {"p2pkh_c": "1bbb", "p2wpkh": "bc1qbbb"}),
    ]
    checker.check_batch(wallets)

    assert looked_up == [["1aaa", "1bbb", "bc1qaaa", "bc1qbbb"]]


def test_database_hit_verifies_via_blockstream(monkeypatch):
    monkeypatch.setattr(config, "CHECK_MODE", "database")

    monkeypatch.setattr(checker, "_db_conn", lambda: object())
    monkeypatch.setattr(db_module, "addresses_with_funds", lambda conn, addrs: {"1hit"})

    called = []
    monkeypatch.setattr(
        checker, "check_balance_blockstream", lambda addr: called.append(addr) or 2.5
    )

    wallet = make_wallet(1, {"p2pkh_c": "1hit", "p2wpkh": "bc1qmiss"})
    hits = checker.check_batch([wallet])

    assert called == ["1hit"]
    assert len(hits) == 1
    assert hits[0].address == "1hit"
    assert hits[0].addr_type == "p2pkh_c"
    assert hits[0].balance == 2.5


def test_database_error_resets_connection_and_reraises(monkeypatch):
    monkeypatch.setattr(config, "CHECK_MODE", "database")

    closed = []

    class FakeConn:
        def close(self):
            closed.append(True)

    checker._conn = FakeConn()
    monkeypatch.setattr(checker, "_db_conn", lambda: checker._conn)

    def boom(conn, addrs):
        raise psycopg.OperationalError("connection lost")

    monkeypatch.setattr(db_module, "addresses_with_funds", boom)

    with pytest.raises(psycopg.OperationalError):
        checker.check_batch([make_wallet(1, {"p2pkh_c": "1abc"})])

    # Broken connection was closed and cleared so the next call reconnects.
    assert closed == [True]
    assert checker._conn is None


def test_maybe_refresh_noop_in_live_mode(monkeypatch):
    monkeypatch.setattr(config, "CHECK_MODE", "live")
    monkeypatch.setattr(config, "DUMP_MAX_AGE_DAYS", 1)
    monkeypatch.setattr(
        db_module, "refresh_dataset", lambda conn: pytest.fail("should not refresh")
    )
    checker.maybe_refresh_dataset()


def test_maybe_refresh_noop_when_disabled(monkeypatch):
    from datetime import UTC, datetime, timedelta

    monkeypatch.setattr(config, "CHECK_MODE", "database")
    monkeypatch.setattr(config, "DUMP_MAX_AGE_DAYS", 0)
    checker._dump_loaded_at = datetime.now(UTC) - timedelta(days=999)
    monkeypatch.setattr(
        db_module, "refresh_dataset", lambda conn: pytest.fail("should not refresh")
    )
    checker.maybe_refresh_dataset()


def test_maybe_refresh_when_stale(monkeypatch):
    from datetime import UTC, datetime, timedelta

    monkeypatch.setattr(config, "CHECK_MODE", "database")
    monkeypatch.setattr(config, "DUMP_MAX_AGE_DAYS", 7)
    monkeypatch.setattr(checker, "_db_conn", lambda: object())
    checker._dump_loaded_at = datetime.now(UTC) - timedelta(days=8)

    refreshed = []
    monkeypatch.setattr(db_module, "refresh_dataset", lambda conn: refreshed.append(True) or 1)

    checker.maybe_refresh_dataset()

    assert refreshed == [True]
    assert checker._dump_loaded_at > datetime.now(UTC) - timedelta(minutes=1)


def test_maybe_refresh_skips_fresh_dump(monkeypatch):
    from datetime import UTC, datetime, timedelta

    monkeypatch.setattr(config, "CHECK_MODE", "database")
    monkeypatch.setattr(config, "DUMP_MAX_AGE_DAYS", 7)
    checker._dump_loaded_at = datetime.now(UTC) - timedelta(days=1)
    monkeypatch.setattr(
        db_module, "refresh_dataset", lambda conn: pytest.fail("should not refresh")
    )
    checker.maybe_refresh_dataset()
