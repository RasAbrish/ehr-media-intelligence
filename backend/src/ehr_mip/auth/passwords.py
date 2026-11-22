"""scrypt password hashes from the standard library (ADR-013, OWASP settings).

Stored as ``scrypt$N$r$p$salt_hex$hash_hex``. N=2^14, r=8, p=5 needs about 16 MB.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from ehr_mip.errors import EhrMipError

N, R, P = 2**14, 8, 5
SALT_BYTES = 16
KEY_BYTES = 32
MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 256
_MAXMEM = 64 * 1024 * 1024


class PasswordTooShortError(EhrMipError):
    code = "password_too_short"


def _derive(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(
        password.encode(), salt=salt, n=n, r=r, p=p, maxmem=_MAXMEM, dklen=KEY_BYTES
    )


def hash_password(password: str) -> str:
    if len(password) < MIN_PASSWORD_LENGTH:
        msg = f"Passwords need at least {MIN_PASSWORD_LENGTH} characters."
        raise PasswordTooShortError(msg)
    salt = secrets.token_bytes(SALT_BYTES)
    return f"scrypt${N}${R}${P}${salt.hex()}${_derive(password, salt, N, R, P).hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time check. Anything that is not our exact format never verifies."""
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt" or (int(n), int(r), int(p)) != (N, R, P):
            return False
        expected = bytes.fromhex(digest)
        actual = _derive(password[:MAX_PASSWORD_LENGTH], bytes.fromhex(salt), N, R, P)
    except ValueError:
        return False
    return hmac.compare_digest(actual, expected)


# Checked against for unknown emails, so they cost the same time as a wrong password.
DUMMY_HASH = f"scrypt${N}${R}${P}${'00' * SALT_BYTES}${'00' * KEY_BYTES}"
