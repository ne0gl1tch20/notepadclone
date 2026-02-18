from __future__ import annotations

import base64
import hashlib
import hmac


def b64encode_bytes(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii")


def b64decode_text(data: str) -> bytes:
    return base64.urlsafe_b64decode(data.encode("ascii"))


def derive_key_pbkdf2(password: str, salt: bytes, rounds: int, dklen: int = 32) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds, dklen=dklen)


def hmac_digest(key: bytes, data: bytes) -> bytes:
    return hmac.new(key, data, hashlib.sha256).digest()


def compare_digest(a: bytes, b: bytes) -> bool:
    return hmac.compare_digest(a, b)


def xor_bytes(left: bytes, right: bytes) -> bytes:
    return bytes(a ^ b for a, b in zip(left, right))


def hmac_counter_keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        block = hmac_digest(key, nonce + counter.to_bytes(8, "big"))
        out.extend(block)
        counter += 1
    return bytes(out[:length])