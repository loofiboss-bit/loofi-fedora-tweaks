#!/usr/bin/env python3
"""Check the retained English Qt string inventory's source locations.

This catalog is not a complete extraction of the current UI and is not used at
runtime. ``--prune-stale-locations`` removes references to deleted files or
line numbers and messages that have no remaining source location.
"""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "loofi-fedora-tweaks" / "resources" / "translations" / "en.ts"
MESSAGE_BLOCK = re.compile(
    r"(?P<open>^[ \t]*<message>[ \t]*\r?\n)(?P<body>.*?)(?P<close>^[ \t]*</message>[ \t]*\r?\n?)",
    re.DOTALL | re.MULTILINE,
)
LOCATION = re.compile(
    r"^[ \t]*<location\s+filename=\"(?P<filename>[^\"]+)\"\s+line=\"(?P<line>\d+)\"\s*/>[ \t]*\r?\n?",
    re.MULTILINE,
)


def _stale_location(filename: str, line: str) -> str | None:
    candidate = (CATALOG.parent / filename).resolve()
    if not candidate.is_relative_to(ROOT.resolve()):
        return "source path leaves the repository"
    if not candidate.is_file():
        return "source file does not exist"
    try:
        line_count = sum(1 for _ in candidate.open("r", encoding="utf-8"))
    except (OSError, UnicodeError):
        return "source file cannot be read"
    if int(line) > line_count:
        return f"source line {line} is beyond the {line_count}-line file"
    return None


def _prune(catalog_text: str) -> tuple[str, int, int]:
    removed_locations = 0
    removed_messages = 0

    def clean_message(match: re.Match[str]) -> str:
        nonlocal removed_locations, removed_messages
        body = match.group("body")
        had_locations = "<location " in body

        def keep_location(location: re.Match[str]) -> str:
            nonlocal removed_locations
            reason = _stale_location(location.group("filename"), location.group("line"))
            if reason:
                removed_locations += 1
                return ""
            return location.group(0)

        cleaned = LOCATION.sub(keep_location, body)
        if had_locations and "<location " not in cleaned:
            removed_messages += 1
            return ""
        return match.group("open") + cleaned + match.group("close")

    cleaned = MESSAGE_BLOCK.sub(clean_message, catalog_text)
    cleaned = re.sub(r"</context>[ \t]*<context>", "</context>\n<context>", cleaned)
    cleaned = cleaned.replace("</context></TS>", "</context>\n</TS>")
    return cleaned, removed_locations, removed_messages


def check(catalog: Path = CATALOG) -> list[str]:
    """Return malformed or stale locator diagnostics for a Qt Linguist file."""
    try:
        tree = ET.parse(catalog)
    except (OSError, ET.ParseError) as error:
        return [f"cannot parse {catalog}: {error}"]
    issues: list[str] = []
    for location in tree.findall(".//location"):
        filename = location.get("filename", "")
        line = location.get("line", "")
        if not filename or not line.isdigit():
            issues.append("translation location is missing a filename or line number")
            continue
        reason = _stale_location(filename, line)
        if reason:
            issues.append(f"{filename}:{line}: {reason}")
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if any source locator is stale (the default).")
    parser.add_argument("--prune-stale-locations", action="store_true", help="Remove stale source locators and orphaned messages.")
    args = parser.parse_args(argv)
    if args.check and args.prune_stale_locations:
        parser.error("choose either --check or --prune-stale-locations")
    if args.prune_stale_locations:
        text = CATALOG.read_text(encoding="utf-8")
        cleaned, locations, messages = _prune(text)
        if locations:
            CATALOG.write_text(cleaned, encoding="utf-8")
        print(f"Removed {locations} stale source locations and {messages} orphaned messages.")
    issues = check()
    if issues:
        for issue in issues:
            print(f"[translation-inventory] ERROR: {issue}", file=sys.stderr)
        return 1
    print("[translation-inventory] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
