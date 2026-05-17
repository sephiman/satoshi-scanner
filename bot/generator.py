import hashlib

import base58
from coincurve import PrivateKey


def generate_random_wallet():
    pk = PrivateKey()
    priv_key = pk.secret
    pub_key = pk.public_key.format(compressed=False)  # 65 bytes, 0x04 || X || Y

    sha256 = hashlib.sha256(pub_key).digest()
    ripemd160 = hashlib.new('ripemd160', sha256).digest()
    prefixed = b'\x00' + ripemd160
    checksum = hashlib.sha256(hashlib.sha256(prefixed).digest()).digest()[:4]
    addr = base58.b58encode(prefixed + checksum).decode()

    return priv_key.hex(), pub_key.hex(), addr
