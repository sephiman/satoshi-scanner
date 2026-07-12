import signal

import pytest

import config
import main
from checker import Hit
from generator import Wallet

WALLET = Wallet(
    priv_hex="ab" * 32,
    pub_compressed_hex="02" + "cd" * 32,
    pub_uncompressed_hex="04" + "cd" * 64,
    addresses={"p2pkh_c": "1addr", "p2wpkh": "bc1qaddr"},
)
HIT = Hit(wallet=WALLET, address="1addr", addr_type="p2pkh_c", balance=1.25)


@pytest.fixture(autouse=True)
def clear_shutdown():
    main._shutdown.clear()
    yield
    main._shutdown.clear()


def test_handle_signal_sets_shutdown_event():
    main._handle_signal(signal.SIGTERM, None)
    assert main._shutdown.is_set()


def test_scan_once_no_hits_sends_nothing(monkeypatch):
    monkeypatch.setattr(main, "generate_wallet", lambda: WALLET)
    monkeypatch.setattr(main.checker, "check_batch", lambda wallets: [])
    sent = []
    monkeypatch.setattr(main, "send_to_telegram", lambda msg, retries=0: sent.append(msg))
    monkeypatch.setattr(main.found, "record", lambda hit: pytest.fail("nothing to record"))

    main.scan_once()

    assert sent == []


def test_scan_once_persists_before_alerting(monkeypatch):
    monkeypatch.setattr(main, "generate_wallet", lambda: WALLET)
    monkeypatch.setattr(main.checker, "check_batch", lambda wallets: [HIT])

    events = []
    monkeypatch.setattr(main.found, "record", lambda hit: events.append(("record", hit)))
    monkeypatch.setattr(
        main,
        "send_to_telegram",
        lambda msg, retries=0: events.append(("telegram", msg, retries)),
    )

    main.scan_once()

    assert events[0] == ("record", HIT)
    assert events[1][0] == "telegram"
    assert "1addr" in events[1][1]
    assert events[1][2] == main.ALERT_RETRIES


def test_scan_once_uses_batch_size_in_database_mode(monkeypatch):
    monkeypatch.setattr(config, "CHECK_MODE", "database")
    monkeypatch.setattr(config, "BATCH_SIZE", 5)

    generated = []
    monkeypatch.setattr(main, "generate_wallet", lambda: generated.append(1) or WALLET)
    monkeypatch.setattr(main.checker, "check_batch", lambda wallets: [])

    main.scan_once()

    assert len(generated) == 5


def test_scan_once_single_key_in_live_mode(monkeypatch):
    monkeypatch.setattr(config, "CHECK_MODE", "live")
    monkeypatch.setattr(config, "BATCH_SIZE", 5)

    generated = []
    monkeypatch.setattr(main, "generate_wallet", lambda: generated.append(1) or WALLET)
    monkeypatch.setattr(main.checker, "check_batch", lambda wallets: [])

    main.scan_once()

    assert len(generated) == 1


def test_main_runs_until_shutdown_and_closes(monkeypatch):
    monkeypatch.setattr(main, "start_http_server", lambda port: None)
    monkeypatch.setattr(main.checker, "init", lambda: None)
    monkeypatch.setattr(main.checker, "maybe_refresh_dataset", lambda: None)
    monkeypatch.setattr(main, "send_to_telegram", lambda msg, retries=0: True)
    monkeypatch.setattr(config, "SCAN_INTERVAL", 0.0)

    closed = []
    monkeypatch.setattr(main.checker, "close", lambda: closed.append(True))

    iterations = []

    def fake_scan():
        iterations.append(1)
        if len(iterations) >= 3:
            main._shutdown.set()

    monkeypatch.setattr(main, "scan_once", fake_scan)

    main.main()

    assert len(iterations) == 3
    assert closed == [True]


def test_main_survives_scan_errors(monkeypatch):
    monkeypatch.setattr(main, "start_http_server", lambda port: None)
    monkeypatch.setattr(main.checker, "init", lambda: None)
    monkeypatch.setattr(main.checker, "maybe_refresh_dataset", lambda: None)
    monkeypatch.setattr(main.checker, "close", lambda: None)
    monkeypatch.setattr(main, "send_to_telegram", lambda msg, retries=0: True)
    monkeypatch.setattr(config, "SCAN_INTERVAL", 0.0)

    iterations = []

    def flaky_scan():
        iterations.append(1)
        if len(iterations) >= 3:
            main._shutdown.set()
        raise RuntimeError("boom")

    monkeypatch.setattr(main, "scan_once", flaky_scan)

    main.main()  # must not raise

    assert len(iterations) == 3


def test_format_alert_contains_fields():
    msg = main.format_alert(HIT)

    assert "*Wallet Found\\!*" in msg
    assert "`1addr`" in msg
    assert "`p2pkh_c`" in msg
    assert "1.25 BTC" in msg
    assert f"`{WALLET.priv_hex}`" in msg
    assert f"`{WALLET.pub_compressed_hex}`" in msg
    assert "blockstream.info/address/1addr" in msg
