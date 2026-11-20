"""Person name parsing (rule ``name.normalize``).

Handles ``FAMILY, GIVEN MIDDLE`` and ``Given Middle Family``, strips titles and
extra whitespace, and title-cases with care for ``McDonald``, ``O'Brien`` and
hyphenated names.
"""

from __future__ import annotations

from dataclasses import dataclass

from ehr_mip.ingestion.audit import Cleaned, Note

_TITLES = {"dr", "mr", "mrs", "ms", "mx", "miss", "prof"}
_SUFFIXES = {"jr": "Jr.", "sr": "Sr.", "ii": "II", "iii": "III", "iv": "IV"}


@dataclass(frozen=True, slots=True)
class PersonName:
    family: str
    given: tuple[str, ...]
    suffix: str | None = None

    @property
    def first_given(self) -> str | None:
        return self.given[0] if self.given else None

    def display(self) -> str:
        return " ".join((*self.given, self.family, *((self.suffix,) if self.suffix else ())))


def _cap(part: str) -> str:
    lower = part.lower()
    if lower.startswith("mc") and len(lower) > 2:  # noqa: PLR2004
        return "Mc" + lower[2:].capitalize()
    return lower.capitalize()


def _smart_case(word: str) -> str:
    return "-".join("'".join(_cap(p) for p in chunk.split("'")) for chunk in word.split("-"))


def _drop_titles(tokens: list[str]) -> list[str]:
    while tokens and tokens[0].rstrip(".").lower() in _TITLES:
        tokens = tokens[1:]
    return tokens


def _take_suffix(tokens: list[str]) -> tuple[list[str], str | None]:
    """Remove a generational suffix (Jr., Sr., II, III, IV) wherever it appears."""
    suffix = None
    kept: list[str] = []
    for token in tokens:
        canonical = _SUFFIXES.get(token.rstrip(".,").lower())
        if canonical is not None and suffix is None:
            suffix = canonical
        else:
            kept.append(token)
    return kept, suffix


def _clean_token(token: str) -> str:
    return _smart_case(token.rstrip("."))


def normalize_name(raw: str | None) -> Cleaned[PersonName | None]:
    if raw is None or not raw.strip():
        return Cleaned(None, (Note("field.missing", "info", "Name is missing."),))
    text = " ".join(raw.split())
    if "," in text:
        family_part, given_part = (p.strip() for p in text.split(",", 1))
        family_tokens, family_suffix = _take_suffix(_drop_titles(family_part.split()))
        given_tokens, given_suffix = _take_suffix(_drop_titles(given_part.split()))
        suffix = family_suffix or given_suffix
    else:
        tokens, suffix = _take_suffix(_drop_titles(text.split()))
        family_tokens, given_tokens = tokens[-1:], tokens[:-1]
    family = " ".join(_clean_token(t) for t in family_tokens)
    given = tuple(_clean_token(t) for t in given_tokens if t.rstrip("."))
    if not family:
        return Cleaned(None, (Note("field.missing", "info", "Name is missing."),))
    name = PersonName(family=family, given=given, suffix=suffix)
    if raw == name.display():
        return Cleaned(name)
    note = Note("name.normalize", "info", "Parsed and normalized the name.", raw, name.display())
    return Cleaned(name, (note,))
