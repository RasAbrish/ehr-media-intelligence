"""Small helpers shared by the mappers."""

from __future__ import annotations

import base64
import hashlib
from datetime import date, datetime
from typing import Any

from ehr_mip.fhir.ids import reference


def ref(resource_id: str) -> dict[str, str]:
    return {"reference": reference(resource_id)}


def fhir_datetime(value: datetime | date | None) -> str | None:
    """FHIR ``dateTime``: keeps date-only values as dates, times with their offset."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    return value.isoformat()


def fhir_instant(value: datetime | date | None) -> str | None:
    """FHIR ``instant`` needs a time: date-only values give None instead of an invented time."""
    return value.isoformat(timespec="seconds") if isinstance(value, datetime) else None


def coding(system: str, code: str, display: str | None = None) -> dict[str, str]:
    item = {"system": system, "code": code}
    if display:
        item["display"] = display
    return item


def concept(
    system: str, code: str, display: str | None = None, text: str | None = None
) -> dict[str, Any]:
    value: dict[str, Any] = {"coding": [coding(system, code, display)]}
    if text:
        value["text"] = text
    return value


def text_attachment(
    text: str, title: str | None, creation: datetime | date | None
) -> dict[str, Any]:
    """Plain-text attachment with size and SHA-1 hash, as FHIR Attachment defines them."""
    raw = text.encode("utf-8")
    attachment: dict[str, Any] = {
        "contentType": "text/plain; charset=utf-8",
        "data": base64.b64encode(raw).decode("ascii"),
        "size": len(raw),
        # FHIR Attachment.hash is defined as SHA-1; it is an integrity check, not security.
        "hash": base64.b64encode(hashlib.sha1(raw).digest()).decode("ascii"),  # noqa: S324
    }
    if title:
        attachment["title"] = title
    created = fhir_datetime(creation)
    if created:
        attachment["creation"] = created
    return attachment


def period(start: datetime | date | None, end: datetime | date | None) -> dict[str, str] | None:
    value = {k: v for k, v in (("start", fhir_datetime(start)), ("end", fhir_datetime(end))) if v}
    return value or None
