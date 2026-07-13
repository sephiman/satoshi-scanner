"""Wallet generation: one random private key, several common address forms.

A single secp256k1 private key maps to multiple Bitcoin addresses depending on
how the public key is encoded and which script type wraps it. Deriving all of
them per key multiplies scan coverage at negligible cost:

  p2pkh_u     legacy 1... from the uncompressed public key
  p2pkh_c     legacy 1... from the compressed public key (most funded legacy)
  p2sh_p2wpkh nested segwit 3... (BIP49)
  p2wpkh      native segwit bc1q... (BIP84)
  p2tr        taproot bc1p... (BIP86 key-path, BIP341 tweak)
"""
import hashlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import base58
from coincurve import PrivateKey, PublicKey

import config

KNOWN_ADDRESS_TYPES = ("p2pkh_u", "p2pkh_c", "p2sh_p2wpkh", "p2wpkh", "p2tr")

# --- bech32 / bech32m (BIP-173 / BIP-350 reference algorithm) ----------------

_BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_BECH32M_CONST = 0x2BC830A3  # BIP-350: witness v1+ uses bech32m, v0 uses bech32


def _bech32_polymod(values: Iterable[int]) -> int:
    gen = (0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)
    chk = 1
    for value in values:
        top = chk >> 25
        chk = (chk & 0x1FFFFFF) << 5 ^ value
        for i in range(5):
            chk ^= gen[i] if ((top >> i) & 1) else 0
    return chk


def _bech32_hrp_expand(hrp: str) -> list[int]:
    return [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp]


def _bech32_create_checksum(hrp: str, data: list[int], const: int) -> list[int]:
    polymod = _bech32_polymod(_bech32_hrp_expand(hrp) + data + [0] * 6) ^ const
    return [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]


def _convertbits(data: bytes, frombits: int, tobits: int) -> list[int]:
    acc = 0
    bits = 0
    ret: list[int] = []
    maxv = (1 << tobits) - 1
    for value in data:
        acc = (acc << frombits) | value
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            ret.append((acc >> bits) & maxv)
    if bits:
        ret.append((acc << (tobits - bits)) & maxv)
    return ret


def encode_segwit_address(hrp: str, witver: int, witprog: bytes) -> str:
    data = [witver] + _convertbits(witprog, 8, 5)
    const = 1 if witver == 0 else _BECH32M_CONST
    checksum = _bech32_create_checksum(hrp, data, const)
    return hrp + "1" + "".join(_BECH32_CHARSET[d] for d in data + checksum)


# --- hashing / base58 helpers ------------------------------------------------


def _hash160(data: bytes) -> bytes:
    return hashlib.new("ripemd160", hashlib.sha256(data).digest()).digest()


def _b58check(payload: bytes) -> str:
    checksum = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    return base58.b58encode(payload + checksum).decode()


# --- address derivation -------------------------------------------------------


def p2pkh_address(pubkey: bytes) -> str:
    return _b58check(b"\x00" + _hash160(pubkey))


def p2sh_p2wpkh_address(pubkey_compressed: bytes) -> str:
    redeem_script = b"\x00\x14" + _hash160(pubkey_compressed)
    return _b58check(b"\x05" + _hash160(redeem_script))


def p2wpkh_address(pubkey_compressed: bytes) -> str:
    return encode_segwit_address("bc", 0, _hash160(pubkey_compressed))


def _tagged_hash(tag: str, msg: bytes) -> bytes:
    tag_hash = hashlib.sha256(tag.encode()).digest()
    return hashlib.sha256(tag_hash + tag_hash + msg).digest()


def p2tr_address(pubkey_compressed: bytes) -> str:
    """BIP86 key-path-only taproot: Q = lift_x(P) + tagged_hash(TapTweak, x)·G,
    address = bech32m(v1, x(Q)). The x-only internal key implies even Y
    (BIP340), so the point is rebuilt with an 0x02 prefix regardless of the
    original parity."""
    xonly = pubkey_compressed[1:]
    internal = PublicKey(b"\x02" + xonly)
    tweak = _tagged_hash("TapTweak", xonly)
    output_key = internal.add(tweak)
    return encode_segwit_address("bc", 1, output_key.format(compressed=True)[1:])


@dataclass(frozen=True)
class Wallet:
    priv_hex: str
    pub_compressed_hex: str
    pub_uncompressed_hex: str
    addresses: dict[str, str]  # address type -> address


def validate_address_types(types: Sequence[str]) -> None:
    unknown = [t for t in types if t not in KNOWN_ADDRESS_TYPES]
    if unknown:
        raise ValueError(
            f"Unknown ADDRESS_TYPES {unknown}; known types: {', '.join(KNOWN_ADDRESS_TYPES)}"
        )
    if not types:
        raise ValueError("ADDRESS_TYPES must name at least one address type")


def derive_addresses(
    pub_compressed: bytes, pub_uncompressed: bytes, types: Sequence[str]
) -> dict[str, str]:
    out: dict[str, str] = {}
    for t in types:
        if t == "p2pkh_u":
            out[t] = p2pkh_address(pub_uncompressed)
        elif t == "p2pkh_c":
            out[t] = p2pkh_address(pub_compressed)
        elif t == "p2sh_p2wpkh":
            out[t] = p2sh_p2wpkh_address(pub_compressed)
        elif t == "p2wpkh":
            out[t] = p2wpkh_address(pub_compressed)
        elif t == "p2tr":
            out[t] = p2tr_address(pub_compressed)
        else:
            raise ValueError(f"Unknown address type: {t}")
    return out


def generate_wallet(types: Sequence[str] | None = None) -> Wallet:
    if types is None:
        types = config.ADDRESS_TYPES
    pk = PrivateKey()
    pub_c = pk.public_key.format(compressed=True)
    pub_u = pk.public_key.format(compressed=False)
    return Wallet(
        priv_hex=pk.secret.hex(),
        pub_compressed_hex=pub_c.hex(),
        pub_uncompressed_hex=pub_u.hex(),
        addresses=derive_addresses(pub_c, pub_u, types),
    )
