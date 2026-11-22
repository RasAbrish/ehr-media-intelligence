"""Accounts and sessions (ADR-013): sign in, resolve a cookie, sign out."""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from ehr_mip.auth.passwords import DUMMY_HASH, hash_password, verify_password
from ehr_mip.db.users import SessionRepository, UserRepository
from ehr_mip.errors import EhrMipError

TOUCH_EVERY = timedelta(minutes=1)  # fewer writes: last seen moves at most once a minute


class AccountExistsError(EhrMipError):
    code = "account_exists"


@dataclass(frozen=True)
class User:
    email: str
    display_name: str


def normalize_email(email: str) -> str:
    return email.strip().lower()


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _utc_now() -> datetime:
    return datetime.now(UTC)


class AuthService:
    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        session_hours: float,
        idle_minutes: float,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.conn = conn
        self.users = UserRepository(conn)
        self.sessions = SessionRepository(conn)
        self.lifetime = timedelta(hours=session_hours)
        self.idle = timedelta(minutes=idle_minutes)
        self.clock = clock

    def create_user(self, email: str, display_name: str, password: str) -> User:
        email = normalize_email(email)
        if self.users.by_email(email) is not None:
            msg = "An account with this email already exists."
            raise AccountExistsError(msg)
        row = self.users.add(email, display_name.strip(), hash_password(password), self.clock())
        return User(row.email, row.display_name)

    def ensure_account(self, email: str, display_name: str, password: str) -> None:
        """Create the demo account once; an existing account is left as it is."""
        if self.users.by_email(normalize_email(email)) is None:
            self.create_user(email, display_name, password)

    def disable(self, email: str) -> bool:
        return self.users.disable(normalize_email(email))

    def authenticate(self, email: str, password: str) -> User | None:
        row = self.users.by_email(normalize_email(email))
        valid = verify_password(password, row.password_hash if row else DUMMY_HASH)
        if row is None or not valid or row.disabled:
            return None
        return User(row.email, row.display_name)

    def start_session(self, user: User) -> str:
        row = self.users.by_email(user.email)
        if row is None:
            msg = "Unknown account."
            raise EhrMipError(msg)
        token = secrets.token_urlsafe(32)
        now = self.clock()
        self.sessions.create(token_hash(token), row.id, now, now + self.lifetime)
        return token

    def resolve(self, token: str) -> User | None:
        if not token:
            return None
        key = token_hash(token)
        session = self.sessions.get(key)
        if session is None:
            return None
        now = self.clock()
        if (
            session.user.disabled
            or now >= session.expires_at
            or now - session.last_seen_at > self.idle
        ):
            self.sessions.delete(key)
            return None
        if now - session.last_seen_at >= TOUCH_EVERY:
            self.sessions.touch(key, now)
        return User(session.user.email, session.user.display_name)

    def end_session(self, token: str) -> None:
        if token:
            self.sessions.delete(token_hash(token))
