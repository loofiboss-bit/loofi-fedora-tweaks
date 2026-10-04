#!/usr/bin/env python3
"""Check and update the active Loofi Fedora Tweaks version sources."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = PROJECT_ROOT / "loofi-fedora-tweaks" / "version.py"
SPEC_FILE = PROJECT_ROOT / "loofi-fedora-tweaks.spec"
PYPROJECT_FILE = PROJECT_ROOT / "pyproject.toml"
VERSION_PATTERN = re.compile(r'(?m)^(\s*__version__\s*=\s*)(["\'])([^"\']+)(["\']\s*)$')
CODENAME_PATTERN = re.compile(r'(?m)^(\s*__version_codename__\s*=\s*)(["\'])([^"\']*)(["\']\s*)$')
SPEC_PATTERN = re.compile(r"(?m)^(\s*Version:\s*)(\S+)(\s*)$")
PYPROJECT_PATTERN = re.compile(r'(?m)^(\s*version\s*=\s*")([^"]+)("\s*)$')


def _read_one(path: Path, pattern: re.Pattern[str], label: str) -> tuple[str, str]:
    """Read a version field and fail clearly if its source is missing or ambiguous."""
    text = path.read_text(encoding="utf-8")
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise ValueError(f"{label}: expected exactly one version field, found {len(matches)}")
    version_group = 3 if label == "version.py" else 2
    return matches[0].group(version_group), text


def _versions() -> tuple[dict[str, str], dict[str, str]]:
    """Return active versions and source text for version.py, spec, and pyproject."""
    paths = {
        "version.py": VERSION_FILE,
        "spec": SPEC_FILE,
        "pyproject.toml": PYPROJECT_FILE,
    }
    patterns = {
        "version.py": VERSION_PATTERN,
        "spec": SPEC_PATTERN,
        "pyproject.toml": PYPROJECT_PATTERN,
    }
    versions: dict[str, str] = {}
    texts: dict[str, str] = {}
    for label, path in paths.items():
        value, content = _read_one(path, patterns[label], label)
        versions[label] = value
        texts[label] = content
    return versions, texts


def run_consistency_check() -> int:
    """Check that all active version sources exist and agree."""
    try:
        versions, _texts = _versions()
    except (OSError, ValueError) as exc:
        print(f"[FAIL] version sources: {exc}")
        return 1

    for source, version in versions.items():
        print(f"[{ 'OK' if version == versions['version.py'] else 'FAIL' }] {source}: {version}")
    if len(set(versions.values())) != 1:
        print("\nVersion sources do not agree.")
        return 1
    print("\nVersion sources agree.")
    return 0


def update_versions(new_version: str, codename: str | None, *, dry_run: bool) -> int:
    """Update only the three maintained version sources."""
    try:
        versions, texts = _versions()
    except (OSError, ValueError) as exc:
        print(f"ERROR: Cannot read version sources: {exc}")
        return 1

    old_version = versions["version.py"]
    replacements = {
        "version.py": VERSION_PATTERN.subn(rf'\g<1>"{new_version}"', texts["version.py"], count=1)[0],
        "spec": SPEC_PATTERN.subn(rf"\g<1>{new_version}\g<3>", texts["spec"], count=1)[0],
        "pyproject.toml": PYPROJECT_PATTERN.subn(rf'\g<1>{new_version}\g<3>', texts["pyproject.toml"], count=1)[0],
    }
    if codename is not None:
        codename_matches = list(CODENAME_PATTERN.finditer(texts["version.py"]))
        if len(codename_matches) != 1:
            print("ERROR: version.py: expected exactly one codename field")
            return 1
        encoded_codename = json.dumps(codename, ensure_ascii=True)
        replacements["version.py"] = CODENAME_PATTERN.sub(
            lambda match: f"{match.group(1)}{encoded_codename}",
            replacements["version.py"],
            count=1,
        )

    paths = {
        "version.py": VERSION_FILE,
        "spec": SPEC_FILE,
        "pyproject.toml": PYPROJECT_FILE,
    }
    changes = [(label, paths[label], content) for label, content in replacements.items() if content != texts[label]]
    mode = "[DRY RUN] " if dry_run else ""
    print(f"{mode}Bumping version: {old_version} -> {new_version}")
    for label, _path, _content in changes:
        print(f"  {label}: {new_version}" if label != "version.py" or codename is None else f"  {label}: {new_version} ({codename})")
    if not changes:
        print("  (no changes needed)")
    if dry_run:
        print("\nNo files were modified (dry-run mode).")
        return 0

    for _label, path, content in changes:
        path.write_text(content, encoding="utf-8")
    print(f"\nUpdated {len(changes)} active version source(s).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Check or update active project version sources.")
    parser.add_argument("version", nargs="?", help="New version (for example 32.1.0)")
    parser.add_argument("--codename", help="Optional release codename")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing files")
    parser.add_argument("--check", action="store_true", help="Check version.py, the RPM spec, and pyproject.toml")
    args = parser.parse_args()

    if args.check:
        if args.version or args.codename or args.dry_run:
            parser.error("--check cannot be combined with a version, --codename, or --dry-run")
        return run_consistency_check()
    if not args.version:
        parser.error("version is required unless --check is used")
    if re.fullmatch(r"\d+\.\d+\.\d+", args.version) is None:
        print(f"ERROR: Invalid version format '{args.version}'. Expected X.Y.Z")
        return 1
    return update_versions(args.version, args.codename, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
