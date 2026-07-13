#!/usr/bin/env python3
"""Validate release documentation, version sync, and optional workflow artifacts.

CI gate: runs as the ``docs_gate`` job in auto-release.yml.
Checks performed:
  1. version.py == .spec == pyproject.toml  (version sync)
  2. CHANGELOG.md has entry for current version
  3. README.md exists and is non-empty
  4. docs/releases/RELEASE-NOTES-vX.Y.Z.md exists and is non-empty
  5. (optional --require-logs) workflow test-results and run-manifest present
  6. No test files contain hardcoded version/codename assertions (stale test check)
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "loofi-fedora-tweaks" / "version.py"
SPEC_FILE = ROOT / "loofi-fedora-tweaks.spec"
PYPROJECT_FILE = ROOT / "pyproject.toml"
CHANGELOG_FILE = ROOT / "CHANGELOG.md"
README_FILE = ROOT / "README.md"
METAINFO_FILE = ROOT / "loofi-fedora-tweaks.metainfo.xml"
TESTS_DIR = ROOT / "tests"
ROADMAP_FILE = ROOT / "ROADMAP.md"
WORKFLOW_SPECS_DIR = ROOT / ".workflow" / "specs"
RACE_LOCK_FILE = WORKFLOW_SPECS_DIR / ".race-lock.json"
CI_WORKFLOW_FILE = ROOT / ".github" / "workflows" / "ci.yml"
AUTO_RELEASE_WORKFLOW_FILE = ROOT / ".github" / "workflows" / "auto-release.yml"
JUSTFILE = ROOT / "Justfile"
PLUGIN_LOADER_FILE = ROOT / "loofi-fedora-tweaks" / "core" / "plugins" / "loader.py"

VERSION_RE = re.compile(r'__version__\s*=\s*"([^"]+)"')
CODENAME_RE = re.compile(r'__version_codename__\s*=\s*"([^"]+)"')
SPEC_VERSION_RE = re.compile(r"^Version:\s*(\S+)", re.MULTILINE)
PYPROJECT_VERSION_RE = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)
COVERAGE_THRESHOLD_RE = re.compile(r'COVERAGE_THRESHOLD:\s*["\']?(\d+)["\']?')
JUST_COVERAGE_RE = re.compile(r'^coverage_min\s*:=\s*"(\d+)"', re.MULTILINE)

# Matches assertEqual-style assertions containing a literal X.Y.Z string.
_HARDCODED_VERSION_RE = re.compile(
    r"""(?:assertEqual|assertIn|assert\s).*["']\d+\.\d+\.\d+["']"""
)
# Matches assertEqual with __version_codename__ and a capitalized word literal.
_HARDCODED_CODENAME_RE = re.compile(
    r"""assertEqual.*__version_codename__.*["'][A-Z]\w+["']"""
)


def extract_version() -> str:
    content = VERSION_FILE.read_text(encoding="utf-8")
    match = VERSION_RE.search(content)
    if not match:
        raise RuntimeError("Unable to parse __version__ from version.py")
    return match.group(1)


def extract_codename() -> str | None:
    """Extract __version_codename__ from version.py, or None."""
    content = VERSION_FILE.read_text(encoding="utf-8")
    match = CODENAME_RE.search(content)
    return match.group(1) if match else None


def extract_spec_version() -> str:
    content = SPEC_FILE.read_text(encoding="utf-8")
    match = SPEC_VERSION_RE.search(content)
    if not match:
        raise RuntimeError("Unable to parse Version: from spec")
    return match.group(1)


def extract_pyproject_version() -> str | None:
    """Return version from pyproject.toml, or None if file missing."""
    if not PYPROJECT_FILE.exists():
        return None
    content = PYPROJECT_FILE.read_text(encoding="utf-8")
    match = PYPROJECT_VERSION_RE.search(content)
    if not match:
        return None
    return match.group(1)


def workflow_version_tag(version: str) -> str:
    parts = version.split(".")
    if len(parts) >= 3:
        return f"v{parts[0]}.{parts[1]}.{parts[2]}"
    if len(parts) == 2:
        return f"v{parts[0]}.{parts[1]}.0"
    return f"v{parts[0]}.0.0"


def workflow_version_tags(version: str) -> List[str]:
    """Return canonical workflow tag for report lookup (vX.Y.Z only)."""
    return [workflow_version_tag(version)]


def workflow_report_candidates(root: Path, version: str, prefix: str) -> List[Path]:
    """Return all accepted report path candidates for a version."""
    reports_root = root / ".workflow" / "reports"
    return [reports_root / f"{prefix}-{tag}.json" for tag in workflow_version_tags(version)]


def resolve_existing_workflow_report(
    root: Path,
    version: str,
    prefix: str,
) -> tuple[Path | None, List[Path]]:
    """Return first existing report path and all candidates."""
    candidates = workflow_report_candidates(root, version, prefix)
    for candidate in candidates:
        if candidate.exists():
            return candidate, candidates
    return None, candidates


def release_notes_candidates(root: Path, version: str) -> List[Path]:
    name = f"RELEASE-NOTES-v{version}.md"
    return [root / "docs" / "releases" / name, root / name]


def resolve_release_notes_file(root: Path, version: str) -> Path:
    for candidate in release_notes_candidates(root, version):
        if candidate.exists():
            return candidate
    return release_notes_candidates(root, version)[0]


def scan_stale_version_tests(
    tests_dir: Path, version: str, codename: str | None
) -> List[str]:
    """Return errors for test files that hardcode the current version or codename.

    These assertions break on every version bump and must use dynamic checks
    instead (e.g. asserting non-empty, semver format, or importing the value).
    """
    errors: List[str] = []
    if not tests_dir.exists():
        return errors

    for test_file in sorted(tests_dir.glob("test_*.py")):
        try:
            content = test_file.read_text(encoding="utf-8")
        except OSError:
            continue

        for lineno, line in enumerate(content.splitlines(), start=1):
            if "# fixture-version" in line:
                continue
            if version in line and _HARDCODED_VERSION_RE.search(line):
                errors.append(
                    f"stale version assertion in {test_file.name}:{lineno} "
                    f'(hardcodes "{version}")'
                )
            if codename and codename in line and _HARDCODED_CODENAME_RE.search(line):
                errors.append(
                    f"stale codename assertion in {test_file.name}:{lineno} "
                    f'(hardcodes "{codename}")'
                )

    return errors


def _extract_codename() -> str | None:
    """Extract __version_codename__ from version.py, or None."""
    return extract_codename()


def _metric_from_report(report: dict, key: str) -> int | None:
    """Return integer metric from summary first, then top-level fallback."""
    summary = report.get("summary")
    if isinstance(summary, dict):
        value = summary.get(key)
        if isinstance(value, int):
            return value

    aliases = {
        "total_tests": ("total_tests", "total"),
        "failed": ("failed", "failures", "failed_tests", "tests_failed"),
        "errors": ("errors",),
    }
    for alias in aliases.get(key, (key,)):
        value = report.get(alias)
        if isinstance(value, int):
            return value
    return None


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _workflow_threshold(path: Path) -> int | None:
    text = _read_text(path)
    match = COVERAGE_THRESHOLD_RE.search(text)
    return int(match.group(1)) if match else None


def _just_threshold() -> int | None:
    text = _read_text(JUSTFILE)
    match = JUST_COVERAGE_RE.search(text)
    return int(match.group(1)) if match else None


def _coverage_claims(text: str) -> List[int]:
    claims = [int(value) for value in re.findall(r"Coverage-(\d+)(?:%25|%)", text)]
    claims.extend(int(value) for value in re.findall(r"coverage\s+(\d+)%", text, flags=re.IGNORECASE))
    return claims


def _builtin_plugin_count() -> int | None:
    """Return the built-in plugin count from PluginLoader without importing UI modules."""
    try:
        tree = ast.parse(PLUGIN_LOADER_FILE.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "_BUILTIN_PLUGINS":
                    if isinstance(node.value, ast.List):
                        return len(node.value.elts)
    return None


def _tab_count_claims(text: str) -> List[int]:
    return [
        int(match.group(1))
        for match in re.finditer(
            r"\b(\d+)\s+(?:lazy-loaded\s+)?(?:feature\s+)?tabs?\b",
            text,
            flags=re.IGNORECASE,
        )
    ]


def _validate_release_surface(root: Path, version: str, codename: str | None, notes_file: Path) -> List[str]:
    errors: List[str] = []
    tag = f"v{version}"

    readme = _read_text(README_FILE)
    if tag not in readme or (codename and codename not in readme):
        errors.append(f"README missing current release {tag} {codename or ''}".strip())
    if f"releases/tag/{tag}" not in readme:
        errors.append(f"README release badge/link missing {tag}")

    roadmap = _read_text(ROADMAP_FILE)
    active_sections = re.findall(r"^## \[ACTIVE\] v[^\n]+", roadmap, flags=re.MULTILINE)
    current_active = f"## [ACTIVE] {tag}" in roadmap
    current_done = f"## [DONE] {tag}" in roadmap
    if not current_active and not current_done:
        errors.append(f"ROADMAP missing ACTIVE or DONE section for {tag}")
    if current_active and len(active_sections) != 1:
        errors.append(f"ROADMAP must have exactly one ACTIVE release section, found {len(active_sections)}")
    if current_done and active_sections:
        errors.append("ROADMAP closed current release but still has an ACTIVE release section")
    if codename and codename not in roadmap:
        errors.append(f"ROADMAP missing codename {codename}")

    changelog = _read_text(CHANGELOG_FILE)
    if codename and f'"{codename}"' not in changelog:
        errors.append(f"CHANGELOG current entry missing codename {codename}")

    metainfo = _read_text(METAINFO_FILE)
    if f'<release version="{version}"' not in metainfo:
        errors.append(f"AppStream metainfo missing release entry for {version}")
    if codename and f'"{codename}"' not in metainfo:
        errors.append(f"AppStream metainfo missing codename {codename}")

    notes = _read_text(notes_file)
    if codename and codename not in notes:
        errors.append(f"release notes missing codename {codename}")

    tasks_file = WORKFLOW_SPECS_DIR / f"tasks-{tag}.md"
    arch_file = WORKFLOW_SPECS_DIR / f"arch-{tag}.md"
    for path in (tasks_file, arch_file):
        if not path.exists() or not _read_text(path).strip():
            errors.append(f"missing workflow spec: {path.relative_to(root)}")
            continue
        spec_text = _read_text(path)
        if tag not in spec_text:
            errors.append(f"workflow spec {path.name} missing {tag}")
        if codename and codename not in spec_text:
            errors.append(f"workflow spec {path.name} missing codename {codename}")

    if not RACE_LOCK_FILE.exists():
        errors.append(f"missing race lock: {RACE_LOCK_FILE.relative_to(root)}")
    else:
        try:
            lock = json.loads(RACE_LOCK_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            errors.append(f"invalid race lock JSON: {RACE_LOCK_FILE.relative_to(root)}")
        else:
            if lock.get("version") != tag or lock.get("target_version") != tag:
                errors.append(f"race lock does not target {tag}")

    ci_threshold = _workflow_threshold(CI_WORKFLOW_FILE)
    release_threshold = _workflow_threshold(AUTO_RELEASE_WORKFLOW_FILE)
    just_threshold = _just_threshold()
    thresholds = [value for value in (ci_threshold, release_threshold, just_threshold) if value is not None]
    if ci_threshold is None:
        errors.append("CI workflow missing COVERAGE_THRESHOLD")
    if release_threshold is None:
        errors.append("auto-release workflow missing COVERAGE_THRESHOLD")
    if thresholds and len(set(thresholds)) != 1:
        errors.append(f"coverage threshold mismatch: values={thresholds}")
    if thresholds and min(thresholds) < 84:
        errors.append(f"coverage threshold below 84: values={thresholds}")

    ci_text = _read_text(CI_WORKFLOW_FILE)
    if "docs/**" in ci_text or "**/*.md" in ci_text:
        errors.append("CI paths-ignore allows docs-only changes to bypass checks")
    if "docs_gate" not in ci_text or "scripts/check_release_docs.py" not in ci_text:
        errors.append("CI missing docs_gate release-doc validation")

    enforced_threshold = ci_threshold or release_threshold or just_threshold or 0
    for claim in _coverage_claims(readme + "\n" + notes):
        if enforced_threshold and claim > enforced_threshold:
            errors.append(f"docs claim {claim}% coverage but CI enforces {enforced_threshold}%")

    plugin_count = _builtin_plugin_count()
    if plugin_count is not None:
        architecture = _read_text(root / "ARCHITECTURE.md")
        for claim in _tab_count_claims(readme + "\n" + architecture):
            if claim != plugin_count:
                errors.append(f"current docs claim {claim} tabs but PluginLoader defines {plugin_count}")

    spec_text = _read_text(SPEC_FILE)
    if re.search(r'python3\s+-c\s+"import main[^"]*"\s*\|\|', spec_text):
        errors.append("RPM import check must be blocking; remove '|| :' from the import validation")

    return errors


def validate_release_docs(root: Path, *, require_logs: bool) -> List[str]:
    errors: List[str] = []

    try:
        py_version = extract_version()
        spec_version = extract_spec_version()
    except Exception as exc:  # pragma: no cover - defensive parser guard
        return [str(exc)]
    codename = _extract_codename()

    # --- Version sync: version.py vs .spec ---
    if py_version != spec_version:
        errors.append(
            f"version mismatch: version.py={py_version} spec={spec_version}")

    # --- Version sync: version.py vs pyproject.toml ---
    pyproject_version = extract_pyproject_version()
    if pyproject_version is not None and py_version != pyproject_version:
        errors.append(
            f"version mismatch: version.py={py_version} pyproject.toml={pyproject_version}"
        )

    # --- CHANGELOG ---
    if (
        not CHANGELOG_FILE.exists()
        or f"## [{py_version}]" not in CHANGELOG_FILE.read_text(encoding="utf-8")
    ):
        errors.append(f"CHANGELOG missing entry for {py_version}")

    # --- README ---
    if not README_FILE.exists() or not README_FILE.read_text(encoding="utf-8").strip():
        errors.append("README.md missing or empty")

    # --- Release notes ---
    notes_file = resolve_release_notes_file(root, py_version)
    if not notes_file.exists() or not notes_file.read_text(encoding="utf-8").strip():
        expected = release_notes_candidates(root, py_version)[0]
        errors.append(f"missing release notes: {expected.relative_to(root)}")
    else:
        errors.extend(_validate_release_surface(root, py_version, codename, notes_file))

    # --- Workflow artifacts (optional) ---
    if require_logs:
        test_report, test_candidates = resolve_existing_workflow_report(
            root,
            py_version,
            "test-results",
        )
        run_manifest, manifest_candidates = resolve_existing_workflow_report(
            root,
            py_version,
            "run-manifest",
        )

        if test_report is None:
            errors.append(
                f"missing workflow test report: {test_candidates[0]}")
        if run_manifest is None:
            errors.append(
                f"missing workflow run manifest: {manifest_candidates[0]}")

        if run_manifest is not None and run_manifest.exists():
            try:
                payload = json.loads(run_manifest.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                errors.append(f"invalid JSON run manifest: {run_manifest}")
            else:
                phases = payload.get("phases")
                if not isinstance(phases, list) or not phases:
                    errors.append(
                        f"run manifest has no phase entries: {run_manifest}")

        if test_report is not None and test_report.exists():
            try:
                payload = json.loads(test_report.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                errors.append(f"invalid JSON test report: {test_report}")
            else:
                if not isinstance(payload, dict):
                    errors.append(
                        f"invalid test report payload: {test_report}")
                else:
                    total_tests = _metric_from_report(payload, "total_tests")
                    failed = _metric_from_report(payload, "failed")
                    report_errors = _metric_from_report(payload, "errors")
                    status = payload.get("status")

                    if total_tests is None:
                        errors.append(
                            "workflow test report missing total_tests metric"
                        )
                    elif total_tests <= 0:
                        errors.append(
                            "workflow test report has zero executed tests"
                        )

                    if failed is None:
                        errors.append(
                            "workflow test report missing failed metric"
                        )
                    elif failed != 0:
                        errors.append(
                            f"workflow test report indicates failed={failed}"
                        )

                    if report_errors is None:
                        errors.append(
                            "workflow test report missing errors metric"
                        )
                    elif report_errors != 0:
                        errors.append(
                            "workflow test report indicates errors="
                            f"{report_errors}"
                        )

                    if status != "pass":
                        errors.append(
                            "workflow test report status must be 'pass'"
                        )

    # --- Stale version tests ---
    stale_errors = scan_stale_version_tests(TESTS_DIR, py_version, codename)
    errors.extend(stale_errors)

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate release docs and workflow artifacts"
    )
    parser.add_argument(
        "--require-logs",
        action="store_true",
        help="Require workflow run/test artifacts",
    )
    args = parser.parse_args()

    issues = validate_release_docs(ROOT, require_logs=args.require_logs)
    if issues:
        print("[release-doc-check] FAILED")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print("[release-doc-check] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
