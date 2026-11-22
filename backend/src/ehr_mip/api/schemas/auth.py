"""Sign-in (docs/04 section 3a)."""

from __future__ import annotations

from pydantic import Field

from ehr_mip.api.schemas.common import ApiModel


class LoginRequest(ApiModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class CurrentUser(ApiModel):
    email: str
    display_name: str
