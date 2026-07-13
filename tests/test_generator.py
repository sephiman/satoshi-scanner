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
        "p2tr": "bc1pmfr3p9j00pfxjh0zmgp99y8zftmd3s5pmedqhyptwy6lm87hf5sspknck9",
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
    assert wallet.addresses["p2tr"].startswith("bc1p")


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


# BIP-86 official test vectors: (x-only internal key, x-only output key, address)
BIP86_VECTORS = [
    (
        "cc8a4bc64d897bddc5fbc2f670f7a8ba0b386779106cf1223c6fc5d7cd6fc115",
        "a60869f0dbcf1dc659c9cecbaf8050135ea9e8cdc487053f1dc6880949dc684c",
        "bc1p5cyxnuxmeuwuvkwfem96lqzszd02n6xdcjrs20cac6yqjjwudpxqkedrcr",
    ),
    (
        "83dfe85a3151d2517290da461fe2815591ef69f2b18a2ce63f01697a8b313145",
        "a82f29944d65b86ae6b5e5cc75e294ead6c59391a1edc5e016e3498c67fc7bbb",
        "bc1p4qhjn9zdvkux4e44uhx8tc55attvtyu358kutcqkudyccelu0was9fqzwh",
    ),
    (
        "399f1b2f4393f29a18c937859c5dd8a77350103157eb880f02e8c08214277cef",
        "882d74e5d0572d5a816cef0041a96b6c1de832f6f9676d9605c44d5e9a97d3dc",
        "bc1p3qkhfews2uk44qtvauqyr2ttdsw7svhkl9nkm9s9c3x4ax5h60wqwruhk7",
    ),
]


@pytest.mark.parametrize("xonly_hex,output_key_hex,address", BIP86_VECTORS)
def test_bip86_taproot_vectors(xonly_hex, output_key_hex, address):
    xonly = bytes.fromhex(xonly_hex)

    # The x-only internal key ignores parity: both prefixes must agree.
    assert generator.p2tr_address(b"\x02" + xonly) == address
    assert generator.p2tr_address(b"\x03" + xonly) == address

    # Intermediate BIP341 tweak check against the published output_key.
    from coincurve import PublicKey

    q = PublicKey(b"\x02" + xonly).add(generator._tagged_hash("TapTweak", xonly))
    assert q.format(compressed=True)[1:].hex() == output_key_hex
