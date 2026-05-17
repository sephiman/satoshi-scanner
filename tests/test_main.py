import main


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
