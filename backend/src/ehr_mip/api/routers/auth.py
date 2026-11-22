"""``/auth/login``, ``/auth/logout``, ``/auth/me`` (docs/04 section 3a)."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Request, Response

from ehr_mip.api.auth import COOKIE, auth_service, require_user
from ehr_mip.api.deps import get_conn, get_state
from ehr_mip.api.errors import ApiProblem
from ehr_mip.api.schemas.auth import CurrentUser, LoginRequest
from ehr_mip.auth.service import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=CurrentUser, summary="Sign in")
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    conn: sqlite3.Connection = Depends(get_conn),
) -> CurrentUser:
    settings = get_state(request).settings
    service = auth_service(conn, settings)
    user = service.authenticate(body.email, body.password)
    if user is None:
        raise ApiProblem(
            401, "invalid_credentials", "Sign-in failed", "Email or password is incorrect."
        )
    response.set_cookie(
        COOKIE,
        service.start_session(user),
        httponly=True,
        samesite="strict",
        secure=settings.env == "prod",
        path="/",
    )
    return CurrentUser(email=user.email, display_name=user.display_name)


@router.post("/logout", status_code=204, summary="Sign out")
async def logout(request: Request, conn: sqlite3.Connection = Depends(get_conn)) -> Response:
    settings = get_state(request).settings
    auth_service(conn, settings).end_session(request.cookies.get(COOKIE, ""))
    response = Response(status_code=204)
    response.delete_cookie(
        COOKIE, path="/", httponly=True, samesite="strict", secure=settings.env == "prod"
    )
    return response


@router.get("/me", response_model=CurrentUser, summary="The signed-in user")
async def me(user: User = Depends(require_user)) -> CurrentUser:
    return CurrentUser(email=user.email, display_name=user.display_name)
