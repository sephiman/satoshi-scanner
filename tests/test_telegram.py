import pytest
import responses

import config
import telegram

API_URL = "https://api.telegram.org/bottest-token/sendMessage"


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_TOKEN", "test-token")
    monkeypatch.setattr(config, "TELEGRAM_CHAT_ID", "12345")


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(telegram.time, "sleep", lambda s: None)


@responses.activate
def test_send_posts_to_telegram_api(configured):
    responses.add(responses.POST, API_URL, json={"ok": True}, status=200)

    assert telegram.send_to_telegram("hello") is True

    assert len(responses.calls) == 1
    body = responses.calls[0].request.body
    assert b"12345" in body
    assert b"hello" in body
    assert b"MarkdownV2" in body


def test_send_noop_when_unconfigured(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_TOKEN", "")
    monkeypatch.setattr(config, "TELEGRAM_CHAT_ID", "")

    with responses.RequestsMock() as rsps:
        assert telegram.send_to_telegram("hello") is False
        assert len(rsps.calls) == 0


@responses.activate
def test_send_swallows_http_errors(configured):
    responses.add(responses.POST, API_URL, status=500)

    assert telegram.send_to_telegram("hello") is False


@responses.activate
def test_send_retries_until_success(configured):
    responses.add(responses.POST, API_URL, status=500)
    responses.add(responses.POST, API_URL, status=500)
    responses.add(responses.POST, API_URL, json={"ok": True}, status=200)

    assert telegram.send_to_telegram("hello", retries=5) is True
    assert len(responses.calls) == 3


@responses.activate
def test_send_gives_up_after_retries(configured):
    for _ in range(3):
        responses.add(responses.POST, API_URL, status=500)

    assert telegram.send_to_telegram("hello", retries=2) is False
    assert len(responses.calls) == 3


def test_escape_markdown():
    assert telegram.escape_markdown("a_b*c[d]e.f!g") == r"a\_b\*c\[d\]e\.f\!g"
    assert telegram.escape_markdown("plain") == "plain"
    # Backslashes themselves are escaped first, not doubled by later passes.
    assert telegram.escape_markdown("\\") == "\\\\"
