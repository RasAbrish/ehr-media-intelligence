"""The session gate (docs/04 section 3a, ADR-013)."""

from __future__ import annotations

import sqlite3

from fastapi import Depends, Request

from ehr_mip.api.deps import get_conn, get_state
from ehr_mip.api.errors import ApiProblem
from ehr_mip.auth.service import AuthService, User
from ehr_mip.config import Settings

COOKIE = "ehr_session"
LOCAL_USER = User(email="local@localhost", display_name="Local user")


def auth_service(conn: sqlite3.Connection, settings: Settings) -> AuthService:
    return AuthService(
        conn, session_hours=settings.session_hours, idle_minutes=settings.session_idle_minutes
    )


def not_authenticated() -> ApiProblem:
    return ApiProblem(401, "not_authenticated", "Sign-in required", "Sign in to continue.")


async def require_user(request: Request, conn: sqlite3.Connection = Depends(get_conn)) -> User:
    settings = get_state(request).settings
    if not settings.auth_enabled:
        return LOCAL_USER
    user = auth_service(conn, settings).resolve(request.cookies.get(COOKIE, ""))
    if user is None:
        raise not_authenticated()
    return user
