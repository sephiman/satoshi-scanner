import main


def test_handle_signal_sets_shutdown_event():
    import signal

    main._shutdown.clear()
    try:
        main._handle_signal(signal.SIGTERM, None)
        assert main._shutdown.is_set()
    finally:
        main._shutdown.clear()


def test_scan_once_records_zero_balance(monkeypatch):
    monkeypatch.setattr(main, "generate_random_wallet", lambda: ("priv", "pub", "1addr"))
    monkeypatch.setattr(main.checker, "check_address", lambda addr: 0.0)
    sent = []
    monkeypatch.setattr(main, "send_to_telegram", lambda msg: sent.append(msg))

    main.scan_once()

    assert sent == []


def test_scan_once_alerts_on_hit(monkeypatch):
    monkeypatch.setattr(main, "generate_random_wallet", lambda: ("priv", "pub", "1addr"))
    monkeypatch.setattr(main.checker, "check_address", lambda addr: 1.25)
    sent = []
    monkeypatch.setattr(main, "send_to_telegram", lambda msg: sent.append(msg))

    main.scan_once()

    assert len(sent) == 1
    assert "1addr" in sent[0]
    assert "1.25 BTC" in sent[0]


def test_format_alert_contains_fields():
    msg = main.format_alert(
        "*Wallet Found!*",
        "1BoatSLRHtKNngkdXEeobR76b53LETtpyT",
        0.12345,
        "04abcdef",
        "deadbeef",
    )

    assert "*Wallet Found!*" in msg
    assert "1BoatSLRHtKNngkdXEeobR76b53LETtpyT" in msg
    assert "0.12345 BTC" in msg
    assert "04abcdef" in msg
    assert "deadbeef" in msg
    assert "blockstream.info/address/1BoatSLRHtKNngkdXEeobR76b53LETtpyT" in msg
