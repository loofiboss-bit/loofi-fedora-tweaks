#!/usr/bin/env python3
"""Generate the compatibility requirements file from pyproject metadata."""

from __future__ import annotations

import argparse
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
OUTPUT = ROOT / "requirements.txt"


def render() -> str:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    project = data["project"]
    dependencies = [*project.get("dependencies", []), *project.get("optional-dependencies", {}).get("api", [])]
    return "# Generated from pyproject.toml by scripts/sync_requirements.py; do not edit.\n" + "\n".join(dependencies) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = render()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != expected:
            print("requirements.txt is not synchronized with pyproject.toml")
            return 1
        return 0
    OUTPUT.write_text(expected, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
