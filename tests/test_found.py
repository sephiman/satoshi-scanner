import json

import config
import found
from checker import Hit
from generator import Wallet
from metrics import FOUND_PERSIST_ERRORS_TOTAL

WALLET = Wallet(
    priv_hex="ab" * 32,
    pub_compressed_hex="02" + "cd" * 32,
    pub_uncompressed_hex="04" + "cd" * 64,
    addresses={"p2pkh_c": "1addr"},
)
HIT = Hit(wallet=WALLET, address="1addr", addr_type="p2pkh_c", balance=0.5)


def test_record_appends_json_line(tmp_path, monkeypatch):
    path = tmp_path / "nested" / "found.jsonl"
    monkeypatch.setattr(config, "FOUND_WALLETS_FILE", str(path))

    found.record(HIT)
    found.record(HIT)

    lines = path.read_text().splitlines()
    assert len(lines) == 2
    entry = json.loads(lines[0])
    assert entry["address"] == "1addr"
    assert entry["address_type"] == "p2pkh_c"
    assert entry["balance_btc"] == 0.5
    assert entry["verified"] is True
    assert entry["private_key"] == WALLET.priv_hex
    assert entry["public_key_compressed"] == WALLET.pub_compressed_hex
    assert "found_at" in entry


def test_record_unverified_hit(tmp_path, monkeypatch):
    path = tmp_path / "found.jsonl"
    monkeypatch.setattr(config, "FOUND_WALLETS_FILE", str(path))

    unverified = Hit(wallet=WALLET, address="1addr", addr_type="p2pkh_c", balance=None)
    found.record(unverified)

    entry = json.loads(path.read_text().splitlines()[0])
    assert entry["balance_btc"] is None
    assert entry["verified"] is False


def test_record_never_raises_on_disk_error(tmp_path, monkeypatch):
    # Point the "file" at an existing directory so open() fails.
    monkeypatch.setattr(config, "FOUND_WALLETS_FILE", str(tmp_path))

    before = FOUND_PERSIST_ERRORS_TOTAL._value.get()
    found.record(HIT)  # must not raise
    assert FOUND_PERSIST_ERRORS_TOTAL._value.get() == before + 1
