#!/usr/bin/env python3
"""Render and validate repository-owned wiki mirrors from canonical docs."""

from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MIRRORS = {
    ROOT / "docs" / "BEGINNER_QUICK_GUIDE.md": ROOT / "wiki" / "Getting-Started.md",
}


def drift() -> list[str]:
    """Return canonical-to-wiki mirror mismatches."""
    issues: list[str] = []
    for source, target in MIRRORS.items():
        if not source.exists():
            issues.append(f"canonical source is missing: {source.relative_to(ROOT)}")
            continue
        if not target.exists():
            issues.append(f"wiki mirror is missing: {target.relative_to(ROOT)}")
            continue
        if target.read_bytes() != source.read_bytes():
            issues.append(
                f"{target.relative_to(ROOT)} differs from {source.relative_to(ROOT)}"
            )
    return issues


def render() -> None:
    """Replace each generated wiki mirror with its canonical source."""
    for source, target in MIRRORS.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report drift without updating generated wiki pages",
    )
    args = parser.parse_args()

    if not args.check:
        render()

    issues = drift()
    if issues:
        for issue in issues:
            print(f"[wiki-sync] ERROR: {issue}")
        return 1
    print("[wiki-sync] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
