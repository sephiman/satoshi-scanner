import pytest
import responses

import telegram


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(telegram, "TELEGRAM_TOKEN", "test-token")
    monkeypatch.setattr(telegram, "TELEGRAM_CHAT_ID", "12345")


@responses.activate
def test_send_posts_to_telegram_api(configured):
    responses.add(
        responses.POST,
        "https://api.telegram.org/bottest-token/sendMessage",
        json={"ok": True},
        status=200,
    )

    telegram.send_to_telegram("hello")

    assert len(responses.calls) == 1
    body = responses.calls[0].request.body
    assert b"12345" in body
    assert b"hello" in body
    assert b"Markdown" in body


def test_send_noop_when_unconfigured(monkeypatch):
    monkeypatch.setattr(telegram, "TELEGRAM_TOKEN", None)
    monkeypatch.setattr(telegram, "TELEGRAM_CHAT_ID", None)

    with responses.RequestsMock() as rsps:
        telegram.send_to_telegram("hello")
        assert len(rsps.calls) == 0


@responses.activate
def test_send_swallows_http_errors(configured):
    responses.add(
        responses.POST,
        "https://api.telegram.org/bottest-token/sendMessage",
        status=500,
    )

    telegram.send_to_telegram("hello")
