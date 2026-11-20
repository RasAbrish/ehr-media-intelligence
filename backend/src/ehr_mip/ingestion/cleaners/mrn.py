"""MRN normalization to 8 zero-padded digits (rules ``mrn.normalize``, ``mrn.invalid``)."""

from __future__ import annotations

import re

from ehr_mip.ingestion.audit import Cleaned, Note

MRN_LENGTH = 8


def normalize_mrn(raw: str | None) -> Cleaned[str | None]:
    if raw is None or not raw.strip():
        return Cleaned(None, (Note("field.missing", "info", "MRN is missing."),))
    digits = re.sub(r"\D", "", raw.upper().replace("MRN", ""))
    if not digits or len(digits) > MRN_LENGTH:
        return Cleaned(None, (Note("mrn.invalid", "error", "MRN has no usable digits.", raw),))
    value = digits.zfill(MRN_LENGTH)
    if raw == value:
        return Cleaned(value)
    return Cleaned(value, (Note("mrn.normalize", "info", "Normalized to 8 digits.", raw, value),))
