import hashlib
import os

import base58
import ecdsa


def generate_random_wallet():
    priv_key = os.urandom(32)
    priv_key_hex = priv_key.hex()

    sk = ecdsa.SigningKey.from_string(priv_key, curve=ecdsa.SECP256k1)
    vk = sk.verifying_key
    pub_key = b'\x04' + vk.to_string()
    pub_key_hex = pub_key.hex()

    sha256 = hashlib.sha256(pub_key).digest()
    ripemd160 = hashlib.new('ripemd160', sha256).digest()
    prefixed = b'\x00' + ripemd160
    checksum = hashlib.sha256(hashlib.sha256(prefixed).digest()).digest()[:4]
    addr = base58.b58encode(prefixed + checksum).decode()

    return priv_key_hex, pub_key_hex, addr
