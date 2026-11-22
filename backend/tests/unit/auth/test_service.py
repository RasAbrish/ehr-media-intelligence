"""Accounts and sessions (ADR-013)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ehr_mip.auth.service import AccountExistsError, AuthService
from ehr_mip.db.connection import connect

PASSWORD = "a long enough password"  # noqa: S105 (test value)
START = datetime(2026, 11, 23, 9, 0, tzinfo=UTC)


class Clock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def service(tmp_path: Path, clock: Clock) -> Iterator[AuthService]:
    with closing(connect(tmp_path / "auth.db")) as conn:
        yield AuthService(conn, session_hours=8, idle_minutes=60, clock=clock)


def test_sign_in_and_resolve(service: AuthService) -> None:
    service.create_user("Ana@Example.org ", "Ana Clinician", PASSWORD)
    user = service.authenticate("ana@example.org", PASSWORD)
    assert user is not None
    assert user.email == "ana@example.org"
    token = service.start_session(user)
    assert len(token) >= 43
    resolved = service.resolve(token)
    assert resolved is not None
    assert resolved.display_name == "Ana Clinician"


def test_only_the_token_hash_is_stored(service: AuthService) -> None:
    user = service.create_user("a@example.org", "A", PASSWORD)
    token = service.start_session(user)
    stored = [row[0] for row in service.conn.execute("SELECT token_hash FROM sessions")]
    assert token not in stored
    assert len(stored) == 1


@pytest.mark.parametrize(
    ("email", "password"),
    [("a@example.org", "wrong password value"), ("nobody@example.org", PASSWORD)],
)
def test_bad_credentials(service: AuthService, email: str, password: str) -> None:
    service.create_user("a@example.org", "A", PASSWORD)
    assert service.authenticate(email, password) is None


def test_duplicate_accounts_are_refused(service: AuthService) -> None:
    service.create_user("a@example.org", "A", PASSWORD)
    with pytest.raises(AccountExistsError):
        service.create_user("A@example.org", "Again", PASSWORD)


def test_sessions_end_after_idle_time_and_at_most_after_the_limit(
    service: AuthService, clock: Clock
) -> None:
    user = service.create_user("a@example.org", "A", PASSWORD)
    token = service.start_session(user)
    for _ in range(7):  # active every 59 minutes for 6 h 53 min
        clock.now += timedelta(minutes=59)
        assert service.resolve(token) is not None
    clock.now = START + timedelta(hours=8, seconds=1)
    assert service.resolve(token) is None

    idle = service.start_session(user)
    clock.now += timedelta(minutes=61)
    assert service.resolve(idle) is None


def test_sign_out_and_disable_end_sessions(service: AuthService) -> None:
    user = service.create_user("a@example.org", "A", PASSWORD)
    first = service.start_session(user)
    service.end_session(first)
    assert service.resolve(first) is None
    second = service.start_session(user)
    service.disable("A@example.org")
    assert service.resolve(second) is None
    assert service.authenticate("a@example.org", PASSWORD) is None


def test_demo_account_is_created_once_and_not_overwritten(service: AuthService) -> None:
    service.ensure_account("demo@example.org", "Demo clinician", PASSWORD)
    service.ensure_account("demo@example.org", "Changed", "another long password")
    user = service.authenticate("demo@example.org", PASSWORD)
    assert user is not None
    assert user.display_name == "Demo clinician"


def test_unknown_tokens_resolve_to_nobody(service: AuthService) -> None:
    assert service.resolve("") is None
    assert service.resolve("not-a-real-token") is None
