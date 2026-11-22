"""The deliverable documents are complete (docs/08 sections 5 to 7)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ehr_mip.config import PROJECT_ROOT

DOCS = PROJECT_ROOT / "docs"
ADRS = sorted((DOCS / "decisions").glob("ADR-*.md"))
DELIVERABLES = (
    "README.md",
    "docs/AI_SYSTEM_CARD.md",
    "docs/WRITEUP.md",
    "docs/ux/heuristic-review.md",
)
README_SECTIONS = (
    "Quick start with Docker",
    "Local development",
    "Tests",
    "Pipeline CLI",
    "API",
    "Design decisions",
    "Data and privacy",
    "Project structure",
    "Known limitations",
)
WRITEUP_SECTIONS = (
    "Tradeoffs and why",
    "Security and AI design choices",
    "With more time",
    "FHIR and clinical concepts researched",
    "How summary quality was validated",
)
LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)\)")
DASH_JOIN = re.compile(rf"[{chr(0x2013)}{chr(0x2014)}]| -- | - (?=[a-z])")


def _read(relative: str) -> str:
    return (PROJECT_ROOT / relative).read_text()


def _prose(text: str) -> list[str]:
    lines: list[str] = []
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced:
            lines.append(re.sub(r"`[^`]*`", "", line.lstrip("-* ")))
    return lines


def test_there_are_twelve_decision_records() -> None:
    assert len(ADRS) == 13


@pytest.mark.parametrize("path", ADRS, ids=lambda p: p.stem)
def test_decision_record_is_complete(path: Path) -> None:
    text = path.read_text()
    assert "**Status:** Accepted" in text
    assert "To be written" not in text
    for heading in ("Context", "Decision", "Alternatives rejected", "Consequences"):
        assert f"## {heading}" in text
        body = text.split(f"## {heading}")[1].split("\n## ")[0]
        assert len(body.split()) >= 8, f"{heading} is too thin"


@pytest.mark.parametrize("relative", DELIVERABLES)
def test_local_links_resolve(relative: str) -> None:
    base = (PROJECT_ROOT / relative).parent
    for target in LINK.findall(_read(relative)):
        if target.startswith(("http:", "https:", "#", "mailto:")):
            continue
        assert (base / target.split("#")[0]).exists(), target


@pytest.mark.parametrize("relative", [*DELIVERABLES, *(f"docs/decisions/{p.name}" for p in ADRS)])
def test_no_dash_joined_clauses(relative: str) -> None:
    assert [line for line in _prose(_read(relative)) if DASH_JOIN.search(line)] == []


def test_readme_follows_the_outline() -> None:
    headings = re.findall(r"^## (.+)$", _read("README.md"), flags=re.MULTILINE)
    positions = [headings.index(section) for section in README_SECTIONS]
    assert positions == sorted(positions)


def test_readme_links_the_system_card_and_shows_the_app() -> None:
    readme = _read("README.md")
    assert "(docs/AI_SYSTEM_CARD.md)" in readme
    assert re.search(r"!\[[^\]]+\]\(docs/screenshots/[^)]+\.png\)", readme)


def test_writeup_follows_the_outline() -> None:
    text = _read("docs/WRITEUP.md")
    for section in WRITEUP_SECTIONS:
        assert section in text


def test_writeup_pdf_is_one_page() -> None:
    pdf = (DOCS / "WRITEUP.pdf").read_bytes()
    assert pdf.startswith(b"%PDF-")
    assert len(re.findall(rb"/Type\s*/Page\b", pdf)) == 1
