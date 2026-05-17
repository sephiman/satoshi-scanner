import pytest

import checker


@pytest.fixture(autouse=True)
def reset_checker_state():
    checker._conn = None
    yield
    checker._conn = None


def test_live_mode_calls_blockstream_directly(monkeypatch):
    monkeypatch.setattr(checker, "CHECK_MODE", "live")
    calls = []
    monkeypatch.setattr(
        checker,
        "check_balance_blockstream",
        lambda addr: calls.append(addr) or 0.42,
    )

    result = checker.check_address("1abc")

    assert result == 0.42
    assert calls == ["1abc"]


def test_database_miss_skips_blockstream(monkeypatch):
    monkeypatch.setattr(checker, "CHECK_MODE", "database")

    import db as db_module

    fake_conn = object()
    monkeypatch.setattr(checker, "_db_conn", lambda: fake_conn)
    monkeypatch.setattr(db_module, "address_has_funds", lambda conn, addr: False)

    called = []
    monkeypatch.setattr(
        checker,
        "check_balance_blockstream",
        lambda addr: called.append(addr) or 1.0,
    )

    assert checker.check_address("1abc") == 0.0
    assert called == []


def test_database_hit_verifies_via_blockstream(monkeypatch):
    monkeypatch.setattr(checker, "CHECK_MODE", "database")

    import db as db_module

    fake_conn = object()
    monkeypatch.setattr(checker, "_db_conn", lambda: fake_conn)
    monkeypatch.setattr(db_module, "address_has_funds", lambda conn, addr: True)

    called = []
    monkeypatch.setattr(
        checker,
        "check_balance_blockstream",
        lambda addr: called.append(addr) or 2.5,
    )

    assert checker.check_address("1abc") == 2.5
    assert called == ["1abc"]
