"""Print the CHANGELOG.md section for a version tag (used by the release workflow)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def section(changelog: str, version: str) -> str:
    pattern = re.compile(rf"^## \[{re.escape(version)}\].*?$(.*?)(?=^## \[|\Z)", re.M | re.S)
    match = pattern.search(changelog)
    if not match:
        raise SystemExit(f"No CHANGELOG.md section for {version}")
    return match.group(1).strip()


def main() -> int:
    version = sys.argv[1].removeprefix("v")
    notes = section((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), version)
    sys.stdout.write(notes + "\n\nVerify downloads with the SHA-256 values in SHA256SUMS.txt.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
