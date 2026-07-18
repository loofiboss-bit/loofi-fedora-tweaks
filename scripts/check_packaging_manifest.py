#!/usr/bin/env python3
"""Validate Python packaging metadata and built artifact contents."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"

EXPECTED_SOURCE_SUFFIXES = (
    "main.py",
    "version.py",
    "core/navigation/areas.py",
    "core/navigation/destinations.py",
    "core/navigation/manifest.py",
    "core/navigation/migrations.py",
    "core/navigation/models.py",
    "core/navigation/policy.py",
    "core/plugins/spec.py",
    "core/plugins/components.py",
    "core/executor/command_facade.py",
    "core/executor/command_policy.py",
    "ui/layout_primitives.py",
    "ui/shared_states.py",
    "ui/main_window.py",
    "assets/modern.qss",
    "assets/icons/icon-map.json",
    "assets/icons/svg/update.svg",
    "resources/translations/en.ts",
    "resources/translations/sv.ts",
    "config/org.loofi.fedora-tweaks.policy",
    "agents/cleanup.json",
)

EXPECTED_ROOT_SUFFIXES = (
    "loofi-fedora-tweaks.desktop",
    "loofi-fedora-tweaks.metainfo.xml",
    "loofi-fedora-tweaks.1",
    "loofi-fedora-tweaks-api.service",
)


def _read_pyproject() -> str:
    return PYPROJECT.read_text(encoding="utf-8")


def _static_metadata_errors() -> list[str]:
    text = _read_pyproject()
    checks = {
        'package-dir = { "" = "loofi-fedora-tweaks" }': "pyproject must map top-level packages to loofi-fedora-tweaks/",
        'py-modules = ["main", "version"]': "pyproject must package main.py and version.py as top-level modules",
        'loofi-fedora-tweaks = "main:main"': "console entry point must target main:main",
        "include-package-data = true": "package data must be included",
        '"core*"': "core subpackages must be included",
        '"ui*"': "ui subpackages must be included",
        '"assets*"': "assets package data must be included",
        '"resources*"': "resources package data must be included",
        '"config*"': "config package data must be included",
        '"agents*"': "agents package data must be included",
    }
    return [message for needle, message in checks.items() if needle not in text]


def _build_artifacts(out_dir: Path) -> list[str]:
    if shutil.which("python3") is None and not sys.executable:
        return ["python executable not available for packaging build"]
    result = subprocess.run(
        [sys.executable, "-m", "build", "--sdist", "--wheel", "--outdir", str(out_dir)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()[-5:]
        return ["python -m build failed: " + " | ".join(detail)]
    return []


def _zip_names(path: Path) -> set[str]:
    with zipfile.ZipFile(path) as archive:
        return set(archive.namelist())


def _tar_names(path: Path) -> set[str]:
    with tarfile.open(path) as archive:
        return set(archive.getnames())


def _has_suffix(names: set[str], suffix: str) -> bool:
    return any(name.endswith(suffix) for name in names)


def _artifact_errors(names: set[str], *, artifact: str, wheel: bool) -> list[str]:
    errors: list[str] = []
    for suffix in EXPECTED_SOURCE_SUFFIXES:
        if not _has_suffix(names, suffix):
            errors.append(f"{artifact} missing {suffix}")
    if not wheel:
        for suffix in EXPECTED_ROOT_SUFFIXES:
            if not _has_suffix(names, suffix):
                errors.append(f"{artifact} missing {suffix}")
    if wheel and not any(name.endswith(".dist-info/entry_points.txt") for name in names):
        errors.append(f"{artifact} missing entry_points.txt")
    if wheel and not any(name.endswith(".dist-info/METADATA") for name in names):
        errors.append(f"{artifact} missing METADATA")
    return errors


def validate_packaging(*, build: bool) -> list[str]:
    errors = _static_metadata_errors()
    if not build:
        return errors

    with tempfile.TemporaryDirectory(prefix="loofi-package-check-") as tmp:
        out_dir = Path(tmp)
        build_errors = _build_artifacts(out_dir)
        if build_errors:
            return errors + build_errors

        wheels = sorted(out_dir.glob("*.whl"))
        sdists = sorted(out_dir.glob("*.tar.gz"))
        if not wheels:
            errors.append("build produced no wheel")
        if not sdists:
            errors.append("build produced no sdist")
        if wheels:
            errors.extend(_artifact_errors(_zip_names(wheels[0]), artifact=wheels[0].name, wheel=True))
        if sdists:
            errors.extend(_artifact_errors(_tar_names(sdists[0]), artifact=sdists[0].name, wheel=False))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate package metadata and artifact contents")
    parser.add_argument("--build", action="store_true", help="Build temporary sdist/wheel and inspect contents")
    args = parser.parse_args()
    issues = validate_packaging(build=args.build)
    if issues:
        print("[packaging-manifest] FAILED")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("[packaging-manifest] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
