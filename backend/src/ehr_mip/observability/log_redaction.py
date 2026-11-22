"""structlog processor that keeps PHI out of logs (docs/09 section 6, FR-6.4).

Drops keys that may hold identifiers or note text, and masks anything shaped like
an 8-digit MRN in the remaining string values (dates such as 20250204 included,
which is acceptable for logs).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, MutableMapping
from typing import Any

PHI_KEYS = frozenset(
    {
        "name",
        "family_name",
        "given_names",
        "display_name",
        "mrn",
        "mrns",
        "birth_date",
        "dob",
        "phone",
        "address",
        "text",
        "query",
        "snippet",
        "note",
        "content",
        "email",
        "password",
    }
)
REDACTED = "[redacted]"
_MRN = re.compile(r"(?<!\d)\d{8}(?!\d)")


def _clean(value: Any) -> Any:
    if isinstance(value, str):
        return _MRN.sub("[mrn]", value)
    if isinstance(value, Mapping):
        return {k: REDACTED if k in PHI_KEYS else _clean(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_clean(v) for v in value]
    return value


def redact_phi(_: Any, __: str, event_dict: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    for key in list(event_dict):
        event_dict[key] = REDACTED if key in PHI_KEYS else _clean(event_dict[key])
    return event_dict
