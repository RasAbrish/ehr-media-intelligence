"""Document type classification (rule ``doctype.map``, docs/05 section 1.3).

Keywords are matched as whole words over the source ``doc_type`` and title;
the first matching rule wins. Only the default is audited.
"""

from __future__ import annotations

import re

from ehr_mip.ingestion.audit import Cleaned, Note
from ehr_mip.ingestion.models import DocType

_RULES: list[tuple[DocType, re.Pattern[str]]] = [
    (DocType.PATHOLOGY_REPORT, re.compile(r"\b(PATHOLOGY|BIOPSY)\b")),
    (
        DocType.IMAGING_REPORT,
        re.compile(r"\b(CT|MRI|X-RAY|XRAY|ULTRASOUND|MAMMO\w*|RADIOLOGY|ECHO\w*|ANGIOGRAPHY)\b"),
    ),
    (DocType.LAB_REPORT, re.compile(r"\bLAB(ORATORY)?\b")),
    (DocType.DISCHARGE_SUMMARY, re.compile(r"\bDISCHARGE\b")),
    (DocType.CONSULT_NOTE, re.compile(r"\bCONSULT\w*")),
    (
        DocType.PROGRESS_NOTE,
        re.compile(r"\b(PROGRESS|HISTORY AND PHYSICAL|ED|EMERGENCY|FOLLOW-UP|VISIT)\b|\bH&P\b"),
    ),
]


def classify_doc_type(doc_type: str | None, title: str | None) -> Cleaned[DocType]:
    text = f"{doc_type or ''} {title or ''}".upper()
    for kind, pattern in _RULES:
        if pattern.search(text):
            return Cleaned(kind)
    note = Note(
        "doctype.map",
        "info",
        "No document type keyword found; classified as a scanned document.",
        (doc_type or title or "").strip() or None,
        DocType.SCANNED_DOCUMENT.value,
    )
    return Cleaned(DocType.SCANNED_DOCUMENT, (note,))
