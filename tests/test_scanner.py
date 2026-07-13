import pytest
import requests
import responses

import scanner


@pytest.fixture(autouse=True)
def reset_scanner_state():
    scanner._cooldown_until = 0.0
    scanner._backoff = scanner._INITIAL_BACKOFF
    yield
    scanner._cooldown_until = 0.0
    scanner._backoff = scanner._INITIAL_BACKOFF


@responses.activate
def test_returns_balance_in_btc():
    addr = "1BoatSLRHtKNngkdXEeobR76b53LETtpyT"
    responses.add(
        responses.GET,
        f"https://blockstream.info/api/address/{addr}",
        json={
            "chain_stats": {"funded_txo_sum": 250_000_000, "spent_txo_sum": 100_000_000}
        },
        status=200,
    )

    assert scanner.check_balance_blockstream(addr) == 1.5
    assert scanner._backoff == scanner._INITIAL_BACKOFF


@responses.activate
def test_429_triggers_cooldown_and_doubles_backoff():
    addr = "1abc"
    responses.add(
        responses.GET,
        f"https://blockstream.info/api/address/{addr}",
        status=429,
    )

    initial = scanner._backoff
    result = scanner.check_balance_blockstream(addr)

    assert result is None
    assert scanner._cooldown_until > 0
    assert scanner._backoff == min(initial * 2, scanner._MAX_BACKOFF)


@responses.activate
def test_cooldown_skips_http_call():
    import time

    addr = "1abc"
    scanner._cooldown_until = time.monotonic() + 60

    result = scanner.check_balance_blockstream(addr)

    assert result is None
    assert len(responses.calls) == 0


@responses.activate
def test_http_error_returns_none():
    addr = "1abc"
    responses.add(
        responses.GET,
        f"https://blockstream.info/api/address/{addr}",
        status=500,
    )

    assert scanner.check_balance_blockstream(addr) is None


@responses.activate
def test_network_error_returns_none():
    addr = "1abc"
    responses.add(
        responses.GET,
        f"https://blockstream.info/api/address/{addr}",
        body=requests.ConnectionError("boom"),
    )

    assert scanner.check_balance_blockstream(addr) is None


@responses.activate
def test_success_resets_backoff():
    addr = "1abc"
    scanner._backoff = 80.0

    responses.add(
        responses.GET,
        f"https://blockstream.info/api/address/{addr}",
        json={"chain_stats": {"funded_txo_sum": 0, "spent_txo_sum": 0}},
        status=200,
    )

    scanner.check_balance_blockstream(addr)
    assert scanner._backoff == scanner._INITIAL_BACKOFF


@responses.activate
def test_backoff_capped_at_max():
    addr = "1abc"
    scanner._backoff = scanner._MAX_BACKOFF

    responses.add(
        responses.GET,
        f"https://blockstream.info/api/address/{addr}",
        status=429,
    )

    scanner.check_balance_blockstream(addr)
    assert scanner._backoff == scanner._MAX_BACKOFF
