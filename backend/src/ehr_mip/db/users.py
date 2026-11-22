"""Accounts and sessions (ADR-013). The only SQL for sign-in lives here."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class UserRow:
    id: int
    email: str
    display_name: str
    password_hash: str
    disabled: bool


@dataclass(frozen=True)
class SessionRow:
    user: UserRow
    created_at: datetime
    expires_at: datetime
    last_seen_at: datetime


def _user(row: sqlite3.Row) -> UserRow:
    return UserRow(
        id=row["id"],
        email=row["email"],
        display_name=row["display_name"],
        password_hash=row["password_hash"],
        disabled=bool(row["disabled"]),
    )


class UserRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def by_email(self, email: str) -> UserRow | None:
        row = self.conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return _user(row) if row else None

    def add(self, email: str, display_name: str, password_hash: str, now: datetime) -> UserRow:
        with self.conn:
            self.conn.execute(
                "INSERT INTO users (email, display_name, password_hash, created_at) "
                "VALUES (?, ?, ?, ?)",
                (email, display_name, password_hash, now.isoformat()),
            )
        user = self.by_email(email)
        assert user is not None  # noqa: S101 (inserted just above)
        return user

    def disable(self, email: str) -> bool:
        with self.conn:
            cursor = self.conn.execute("UPDATE users SET disabled = 1 WHERE email = ?", (email,))
            self.conn.execute(
                "DELETE FROM sessions WHERE user_id IN (SELECT id FROM users WHERE email = ?)",
                (email,),
            )
        return cursor.rowcount > 0


class SessionRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def create(self, token_hash: str, user_id: int, now: datetime, expires: datetime) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now.isoformat(),))
            self.conn.execute(
                "INSERT INTO sessions (token_hash, user_id, created_at, expires_at, last_seen_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (token_hash, user_id, now.isoformat(), expires.isoformat(), now.isoformat()),
            )

    def get(self, token_hash: str) -> SessionRow | None:
        row = self.conn.execute(
            "SELECT u.*, s.created_at AS s_created, s.expires_at, s.last_seen_at "
            "FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?",
            (token_hash,),
        ).fetchone()
        if row is None:
            return None
        return SessionRow(
            user=_user(row),
            created_at=datetime.fromisoformat(row["s_created"]),
            expires_at=datetime.fromisoformat(row["expires_at"]),
            last_seen_at=datetime.fromisoformat(row["last_seen_at"]),
        )

    def touch(self, token_hash: str, now: datetime) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE sessions SET last_seen_at = ? WHERE token_hash = ?",
                (now.isoformat(), token_hash),
            )

    def delete(self, token_hash: str) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
