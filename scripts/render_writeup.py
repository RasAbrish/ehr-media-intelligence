"""Render docs/WRITEUP.md to docs/WRITEUP.pdf (docs/08 section 6).

Uses markdown-it-py and the project's Playwright Chromium, so nothing is downloaded. A result
longer than one page is an error and leaves the previous PDF in place.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "WRITEUP.md"
TARGET = ROOT / "docs" / "WRITEUP.pdf"
FRONTEND = ROOT / "frontend"
CSS = """
@page { size: A4; margin: 11mm 14mm; }
body { font: 9.4pt/1.32 "Noto Sans", "DejaVu Sans", sans-serif; color: #15191f; margin: 0; }
h1 { font-size: 15pt; margin: 0 0 4pt; }
h2 { font-size: 10.6pt; margin: 8pt 0 2.5pt; color: #0b5f63; }
p { margin: 0 0 4pt; }
ul { margin: 0 0 4pt; padding-left: 12pt; }
li { margin: 0 0 1.5pt; }
code { font: 8.4pt "Noto Sans Mono", monospace; }
table { width: 100%; border-collapse: collapse; margin: 3pt 0 5pt; font-size: 8pt; }
th, td { border: 0.5pt solid #b9c0c8; padding: 2pt 3pt; text-align: center; }
th { background: #eef1f4; }
"""


def chromium() -> str:
    found = subprocess.run(
        [  # noqa: S607
            "node",
            "-e",
            'process.stdout.write(require("@playwright/test").chromium.executablePath())',
        ],
        cwd=FRONTEND,
        env=os.environ | {"PLAYWRIGHT_BROWSERS_PATH": "0"},
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    if not Path(found).is_file():
        sys.exit(
            "Chromium is missing: cd frontend && "
            "PLAYWRIGHT_BROWSERS_PATH=0 pnpm exec playwright install chromium"
        )
    return found


def page_count(pdf: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page\b", pdf))


def main() -> None:
    body = MarkdownIt("commonmark").enable("table").render(SOURCE.read_text())
    html = (
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        f"<title>EHR Media Intelligence write-up</title><style>{CSS}</style>{body}</html>"
    )
    browser = chromium()
    with tempfile.TemporaryDirectory(prefix="ehr-mip-writeup-") as tmp:
        page, out = Path(tmp) / "writeup.html", Path(tmp) / "writeup.pdf"
        page.write_text(html)
        subprocess.run(  # noqa: S603 (fixed arguments, no shell)
            [
                browser,
                "--headless=new",
                "--disable-gpu",
                f"--user-data-dir={tmp}/profile",
                "--no-pdf-header-footer",
                f"--print-to-pdf={out}",
                page.as_uri(),
            ],
            capture_output=True,
            check=True,
            timeout=90,
        )
        pdf = out.read_bytes()
    pages = page_count(pdf)
    if pages != 1:
        sys.exit(f"The write-up is {pages} pages. It must be one: shorten docs/WRITEUP.md.")
    TARGET.write_bytes(pdf)
    print(f"wrote {TARGET.relative_to(ROOT)} ({pages} page)")


if __name__ == "__main__":
    main()
