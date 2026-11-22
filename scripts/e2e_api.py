"""API for the end-to-end tests, on a throwaway copy of the generated data.

`make e2e` writes (summary feedback), so it never points at the database or the index
that `make dev` serves. The copy is deleted when Playwright stops the server.
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "generated"
# Test values for this throwaway copy only (frontend/e2e/auth.setup.ts uses the same).
E2E_EMAIL = "e2e@example.org"
E2E_PASSWORD = "e2e-test-password"  # noqa: S105


def copy_data(target: Path) -> None:
    db = SOURCE / "ehr_mip.db"
    if not db.exists():
        sys.exit("No indexed data: run `make pipeline` first.")
    source = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    with closing(source), closing(sqlite3.connect(target / "ehr_mip.db")) as copy:
        source.backup(copy)
    shutil.copytree(SOURCE / "chroma", target / "chroma")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8010)
    port = parser.parse_args().port
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    with tempfile.TemporaryDirectory(prefix="ehr-mip-e2e-") as tmp:
        target = Path(tmp)
        copy_data(target)
        env = os.environ | {
            "ANTHROPIC_API_KEY": "",
            "SQLITE_PATH": str(target / "ehr_mip.db"),
            "CHROMA_DIR": str(target / "chroma"),
            "REPORTS_DIR": str(target / "reports"),
            "RATE_LIMIT_ENABLED": "false",  # one client runs every test
            # The browser tests and Lighthouse sign in with this test account.
            "AUTH_ENABLED": "true",
            "DEMO_ACCOUNT_EMAIL": E2E_EMAIL,
            "DEMO_ACCOUNT_PASSWORD": E2E_PASSWORD,
        }
        cli = Path(sys.executable).with_name("ehr-mip")
        server = subprocess.Popen(  # noqa: S603 (fixed arguments, no shell)
            [str(cli), "serve", "--port", str(port)], cwd=ROOT, env=env
        )
        try:
            sys.exit(server.wait())
        finally:
            server.terminate()
            server.wait()


if __name__ == "__main__":
    main()
