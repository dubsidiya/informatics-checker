from __future__ import annotations

import hashlib
import hmac
import os
import secrets

SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32


def hash_pin(pin: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(
        pin.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
    )
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_pin(pin: str, encoded: str) -> bool:
    if not pin or not encoded:
        return False
    try:
        kind, n_s, r_s, p_s, salt_hex, digest_hex = encoded.split("$")
        if kind != "scrypt":
            return False
        expected = bytes.fromhex(digest_hex)
        digest = hashlib.scrypt(
            pin.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=int(n_s),
            r=int(r_s),
            p=int(p_s),
            dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    # Constant-time compare of raw bytes; both sides are the same length by
    # construction (dklen = len(expected)), so no length oracle leaks here.
    return hmac.compare_digest(digest, expected)


def pin_fingerprint(encoded: str) -> str:
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def cookie_flags(*, secure: bool, max_age: int, httponly: bool = True) -> str:
    flags = f"Path=/; SameSite=Strict; Max-Age={max_age}"
    if httponly:
        flags = "HttpOnly; " + flags
    if secure:
        flags += "; Secure"
    return flags
