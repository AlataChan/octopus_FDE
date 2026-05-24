"""stdlib scrypt password hash parsing and verification."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
from dataclasses import dataclass

MIN_SCRYPT_N = 2**14
EXPECTED_R = 8
EXPECTED_P = 1
DKLEN = 32
SCRYPT_MAXMEM = 128 * 1024 * 1024
DUMMY_SCRYPT_HASH = (
    "scrypt$16384$8$1$"
    "bG9vbS1kdW1teS1zYWx0IQ==$"
    "2V+Hd/7y56zWLldUJfhATjt5B+FxwRuixtQOxfjy8Uc="
)


class ScryptPasswordError(ValueError):
    """Raised when a configured scrypt password hash is invalid."""


@dataclass(frozen=True)
class ScryptHash:
    n: int
    r: int
    p: int
    salt: bytes
    digest: bytes


def validate_scrypt_hash(encoded: str) -> None:
    _parse_scrypt_hash(encoded)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=MIN_SCRYPT_N,
        r=EXPECTED_R,
        p=EXPECTED_P,
        dklen=DKLEN,
        maxmem=SCRYPT_MAXMEM,
    )
    return (
        f"scrypt${MIN_SCRYPT_N}${EXPECTED_R}${EXPECTED_P}$"
        f"{base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"
    )


def verify_password(password: str, encoded: str) -> bool:
    parsed = _parse_scrypt_hash(encoded)
    candidate = hashlib.scrypt(
        password.encode("utf-8"),
        salt=parsed.salt,
        n=parsed.n,
        r=parsed.r,
        p=parsed.p,
        dklen=len(parsed.digest),
        maxmem=SCRYPT_MAXMEM,
    )
    return hmac.compare_digest(candidate, parsed.digest)


def _parse_scrypt_hash(encoded: str) -> ScryptHash:
    parts = encoded.split("$")
    if len(parts) != 6 or parts[0] != "scrypt":
        raise ScryptPasswordError("LOOM_AUTH_PASSWORD_HASH must use scrypt$N$r$p$salt_b64$hash_b64 format")
    try:
        n = int(parts[1])
        r = int(parts[2])
        p = int(parts[3])
        salt = base64.b64decode(parts[4], validate=True)
        digest = base64.b64decode(parts[5], validate=True)
    except (ValueError, TypeError) as e:
        raise ScryptPasswordError("LOOM_AUTH_PASSWORD_HASH contains invalid scrypt parameters") from e
    if n < MIN_SCRYPT_N:
        raise ScryptPasswordError("LOOM_AUTH_PASSWORD_HASH scrypt N must be at least 16384")
    if r != EXPECTED_R or p != EXPECTED_P:
        raise ScryptPasswordError("LOOM_AUTH_PASSWORD_HASH must use scrypt r=8 and p=1")
    if not salt or len(digest) < DKLEN:
        raise ScryptPasswordError("LOOM_AUTH_PASSWORD_HASH salt/hash payload is too short")
    return ScryptHash(n=n, r=r, p=p, salt=salt, digest=digest)
