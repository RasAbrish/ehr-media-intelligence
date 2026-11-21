"""Snippets, highlight ranges and the MRN query pattern (docs/05-ALGORITHMS.md 4.2, 4.4)."""

from __future__ import annotations

import re

SNIPPET_CHARS = 320
MRN_QUERY = re.compile(r"^(?:MRN)?[-\s:#]*(?P<digits>\d{4,8})$", re.IGNORECASE)

# Short clinical abbreviations that are kept even though they are under 3 characters.
_ABBREVIATIONS = frozenset(
    {
        "ct",
        "mri",
        "k",
        "na",
        "ef",
        "bp",
        "hr",
        "pe",
        "mi",
        "ed",
        "uti",
        "ckd",
        "aki",
        "ecg",
        "ekg",
        "cbc",
        "bmp",
        "copd",
        "chf",
        "dvt",
    }
)
STOP_WORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "but",
        "by",
        "for",
        "from",
        "has",
        "have",
        "in",
        "into",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "that",
        "the",
        "their",
        "this",
        "to",
        "was",
        "were",
        "will",
        "with",
        "without",
        "patient",
        "patients",
    ]
)
_TOKEN = re.compile(r"[a-z0-9]+(?:[-'][a-z0-9]+)*")


def mrn_digits(query: str) -> str | None:
    """Digits of an MRN-shaped query (``MRN 00012345``, ``12345``), else ``None``."""
    match = MRN_QUERY.match(query.strip())
    return match["digits"] if match else None


def query_terms(query: str) -> list[str]:
    """Lower-case terms worth highlighting: no stop words, ≥ 3 chars or a known abbreviation."""
    terms: list[str] = []
    for token in _TOKEN.findall(query.lower()):
        if token in STOP_WORDS:
            continue
        if (len(token) >= 3 or token in _ABBREVIATIONS) and token not in terms:  # noqa: PLR2004
            terms.append(token)
    return terms


def highlight_ranges(text: str, terms: list[str]) -> list[tuple[int, int]]:
    """Merged ``[start, end)`` ranges of whole-word, case-insensitive term matches."""
    spans: list[tuple[int, int]] = []
    for term in terms:
        pattern = re.compile(rf"(?<![\w]){re.escape(term)}(?![\w])", re.IGNORECASE)
        spans += [(m.start(), m.end()) for m in pattern.finditer(text)]
    spans.sort()
    merged: list[tuple[int, int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def snippet(text: str, terms: list[str], *, limit: int = SNIPPET_CHARS) -> str:
    """At most ``limit`` characters around the first match, cut at word boundaries."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    ranges = highlight_ranges(text, terms)
    start = 0
    if ranges and ranges[0][1] > limit - 40:
        start = max(ranges[0][0] - 60, 0)
        start = text.rfind(" ", 0, start) + 1 if start else 0
    prefix = "…" if start else ""
    budget = limit - len(prefix) - 1  # room for the closing ellipsis
    body = text[start : start + budget]
    if start + budget < len(text):
        body = body.rsplit(" ", 1)[0].rstrip(" ,;:") + "…"
    return prefix + body
