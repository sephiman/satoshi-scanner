from coincurve import PrivateKey

import generator


def test_known_vector_priv_one(monkeypatch):
    fixed = PrivateKey(secret=(1).to_bytes(32, "big"))
    monkeypatch.setattr(generator, "PrivateKey", lambda: fixed)

    priv, pub, addr = generator.generate_random_wallet()

    assert priv == "0000000000000000000000000000000000000000000000000000000000000001"
    assert pub == (
        "0479be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f817"
        "98483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8"
    )
    assert addr == "1EHNa6Q4Jz2uvNExL497mE43ikXhwF6kZm"


def test_random_wallet_shape():
    priv, pub, addr = generator.generate_random_wallet()

    assert len(priv) == 64
    assert len(pub) == 130
    assert pub.startswith("04")
    assert addr.startswith("1")
    assert 26 <= len(addr) <= 35
