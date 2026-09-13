#!/usr/bin/env python3
"""Generate the runtime requirements file from pyproject metadata.

The file is consumed by source checkouts and CI.  Optional integrations are no
longer part of the product surface, so only the application's core runtime
dependencies are mirrored here.  Development tools stay in the ``dev`` extra
and are installed explicitly by the relevant workflow.
"""

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
    dependencies = list(project.get("dependencies", []))
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
