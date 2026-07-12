import pytest
from coincurve import PrivateKey

import generator

# Wallet for private key 1 — all values independently documented:
# p2pkh vectors are the classic "key 1" addresses, p2wpkh is the BIP-173
# reference vector for this exact public key.
PRIV_ONE_HEX = "0000000000000000000000000000000000000000000000000000000000000001"
PUB_C_HEX = "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
PUB_U_HEX = (
    "0479be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f817"
    "98483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8"
)


@pytest.fixture
def priv_one(monkeypatch):
    fixed = PrivateKey(secret=(1).to_bytes(32, "big"))
    monkeypatch.setattr(generator, "PrivateKey", lambda: fixed)


def test_known_vectors_priv_one(priv_one):
    wallet = generator.generate_wallet(types=generator.KNOWN_ADDRESS_TYPES)

    assert wallet.priv_hex == PRIV_ONE_HEX
    assert wallet.pub_compressed_hex == PUB_C_HEX
    assert wallet.pub_uncompressed_hex == PUB_U_HEX
    assert wallet.addresses == {
        "p2pkh_u": "1EHNa6Q4Jz2uvNExL497mE43ikXhwF6kZm",
        "p2pkh_c": "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH",
        "p2sh_p2wpkh": "3JvL6Ymt8MVWiCNHC7oWU6nLeHNJKLZGLN",
        "p2wpkh": "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4",
    }


def test_random_wallet_shape():
    wallet = generator.generate_wallet(types=generator.KNOWN_ADDRESS_TYPES)

    assert len(wallet.priv_hex) == 64
    assert len(wallet.pub_compressed_hex) == 66
    assert wallet.pub_compressed_hex[:2] in ("02", "03")
    assert len(wallet.pub_uncompressed_hex) == 130
    assert wallet.pub_uncompressed_hex.startswith("04")

    assert wallet.addresses["p2pkh_u"].startswith("1")
    assert wallet.addresses["p2pkh_c"].startswith("1")
    assert wallet.addresses["p2sh_p2wpkh"].startswith("3")
    assert wallet.addresses["p2wpkh"].startswith("bc1q")


def test_generate_wallet_respects_requested_types():
    wallet = generator.generate_wallet(types=("p2wpkh",))
    assert list(wallet.addresses) == ["p2wpkh"]


def test_generate_wallet_defaults_to_configured_types(monkeypatch):
    import config

    monkeypatch.setattr(config, "ADDRESS_TYPES", ("p2pkh_c", "p2wpkh"))
    wallet = generator.generate_wallet()
    assert set(wallet.addresses) == {"p2pkh_c", "p2wpkh"}


def test_validate_address_types_rejects_unknown():
    with pytest.raises(ValueError, match="bogus"):
        generator.validate_address_types(("p2pkh_c", "bogus"))


def test_validate_address_types_rejects_empty():
    with pytest.raises(ValueError):
        generator.validate_address_types(())


def test_bip173_bech32_vector():
    # BIP-173: witness v0, program = hash160 of the key-1 compressed pubkey.
    prog = bytes.fromhex("751e76e8199196d454941c45d1b3a323f1433bd6")
    assert (
        generator.encode_segwit_address("bc", 0, prog)
        == "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
    )
