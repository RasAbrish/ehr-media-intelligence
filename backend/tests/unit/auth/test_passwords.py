"""scrypt password hashes (ADR-013)."""

from __future__ import annotations

import pytest

from ehr_mip.auth.passwords import (
    MIN_PASSWORD_LENGTH,
    PasswordTooShortError,
    hash_password,
    verify_password,
)


def test_round_trip_and_format() -> None:
    stored = hash_password("correct horse battery")
    scheme, n, r, p, salt, digest = stored.split("$")
    assert (scheme, n, r, p) == ("scrypt", "16384", "8", "5")
    assert len(bytes.fromhex(salt)) == 16
    assert len(bytes.fromhex(digest)) == 32
    assert verify_password("correct horse battery", stored)
    assert not verify_password("correct horse batterY", stored)


def test_each_hash_has_its_own_salt() -> None:
    assert hash_password("same password here") != hash_password("same password here")


def test_short_passwords_are_refused() -> None:
    with pytest.raises(PasswordTooShortError):
        hash_password("x" * (MIN_PASSWORD_LENGTH - 1))


@pytest.mark.parametrize("stored", ["", "plain", "scrypt$1$2$3$zz$zz", "bcrypt$a$b$c$d$e"])
def test_malformed_hashes_never_verify(stored: str) -> None:
    assert not verify_password("whatever password", stored)
