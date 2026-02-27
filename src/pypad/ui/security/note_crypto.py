from __future__ import annotations

import json
import os

from pypad.core.crypto_helpers import (
    b64decode_text,
    b64encode_bytes,
    compare_digest,
    derive_key_pbkdf2,
    hmac_counter_keystream,
    hmac_digest,
    xor_bytes,
)

HEADER = "ENCNOTE1"
PBKDF2_ROUNDS = 200_000


def _b64encode(data: bytes) -> str:
    return b64encode_bytes(data)


def _b64decode(data: str) -> bytes:
    return b64decode_text(data)


def _derive_key(password: str, salt: bytes) -> bytes:
    return derive_key_pbkdf2(password, salt, rounds=PBKDF2_ROUNDS, dklen=32)


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    return hmac_counter_keystream(key, nonce, length)


def is_encrypted_payload(text: str) -> bool:
    return text.startswith(HEADER + "\n")


def encrypt_text(plain_text: str, password: str) -> str:
    salt = os.urandom(16)
    nonce = os.urandom(16)
    key = _derive_key(password, salt)
    plain = plain_text.encode("utf-8")
    stream = _keystream(key, nonce, len(plain))
    cipher = xor_bytes(plain, stream)
    mac_key = hmac_digest(key, b"mac")
    tag = hmac_digest(mac_key, nonce + cipher)
    payload = {
        "v": 1,
        "s": _b64encode(salt),
        "n": _b64encode(nonce),
        "c": _b64encode(cipher),
        "t": _b64encode(tag),
    }
    return HEADER + "\n" + json.dumps(payload, separators=(",", ":"))


def decrypt_text(payload_text: str, password: str) -> str:
    if not is_encrypted_payload(payload_text):
        raise ValueError("Not an encrypted note payload")
    raw = payload_text.split("\n", 1)[1]
    try:
        payload = json.loads(raw)
        salt = _b64decode(payload["s"])
        nonce = _b64decode(payload["n"])
        cipher = _b64decode(payload["c"])
        tag = _b64decode(payload["t"])
    except Exception as exc:  # noqa: BLE001
        raise ValueError("Invalid encrypted payload") from exc

    key = _derive_key(password, salt)
    mac_key = hmac_digest(key, b"mac")
    expected = hmac_digest(mac_key, nonce + cipher)
    if not compare_digest(tag, expected):
        raise ValueError("Wrong password or corrupted payload")

    stream = _keystream(key, nonce, len(cipher))
    plain = xor_bytes(cipher, stream)
    try:
        return plain.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Decrypted data is invalid UTF-8") from exc

