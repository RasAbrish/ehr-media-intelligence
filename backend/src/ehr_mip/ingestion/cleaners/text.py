"""Clinical text normalization (rule ``text.normalize``).

Audit notes describe what changed but never copy clinical text.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

from ehr_mip.ingestion.audit import Cleaned, Note

_SINGLE_QUOTES = (0x2018, 0x2019, 0x201A, 0x201B, 0x2032)
_DOUBLE_QUOTES = (0x201C, 0x201D, 0x201E, 0x2033)
_SMART = str.maketrans(
    {chr(c): "'" for c in _SINGLE_QUOTES} | {chr(c): '"' for c in _DOUBLE_QUOTES}
)
_MANY_BLANK_LINES = re.compile(r"\n{4,}")


def normalize_text(raw: str) -> Cleaned[str]:
    changes: list[str] = []
    text = unicodedata.normalize("NFC", raw)
    if text != raw:
        changes.append("unicode NFC")
    quoted = text.translate(_SMART)
    if quoted != text:
        changes.append("smart quotes")
    text = quoted
    unified = text.replace("\r\n", "\n").replace("\r", "\n")
    if unified != text:
        changes.append("line endings")
    text = unified
    stripped = "\n".join(line.rstrip() for line in text.split("\n"))
    if stripped != text:
        changes.append("trailing spaces")
    text = _MANY_BLANK_LINES.sub("\n\n", stripped)
    if text != stripped:
        changes.append("blank lines")
    trimmed = text.strip()
    if trimmed != text and "trailing spaces" not in changes:
        changes.append("surrounding whitespace")
    if not changes:
        return Cleaned(trimmed)
    note = Note("text.normalize", "info", "Normalized text: " + ", ".join(changes) + ".")
    return Cleaned(trimmed, (note,))


def content_hash(text: str) -> str:
    """SHA-256 of normalized text: equal hashes mean exact duplicates."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def comparison_text(text: str) -> str:
    """Lower case with collapsed whitespace, for near-duplicate similarity."""
    return " ".join(text.lower().split())
