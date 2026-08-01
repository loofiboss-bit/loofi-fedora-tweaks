#!/usr/bin/env python3
"""Validate immutable Compass v23.0.0 Phase 6 candidate evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "docs" / "reports" / "V23_PHASE6_LOCAL_CANDIDATE.json"
SCREENSHOTS = ROOT / "docs" / "reports" / "V23_PHASE6_SCREENSHOTS.json"
CANDIDATE_RELATIVE = CANDIDATE.relative_to(ROOT).as_posix()

RETAINED_CANDIDATE_VERSION = "23.0.0"
EXPECTED_CODENAME = "Compass"
EXPECTED_RELEASE = "v23.0.0 Compass"
EXPECTED_HEAD = re.compile(r"^[0-9a-f]{40}$")
EXPECTED_DIGEST = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_ARTIFACTS = (
    "loofi-fedora-tweaks-23.0.0-1.fc44.noarch.rpm",
    "loofi-fedora-tweaks-api-23.0.0-1.fc44.noarch.rpm",
    "loofi-fedora-tweaks-daemon-23.0.0-1.fc44.noarch.rpm",
    "loofi-fedora-tweaks-v23.0.0.flatpak",
    "loofi_fedora_tweaks-23.0.0.tar.gz",
)
EXPECTED_SKIPPED_GATES = {
    "fresh_atomic": "open-user-authorized-skip",
    "manual_keyboard": "open-user-authorized-skip",
    "audible_orca": "open-user-authorized-skip",
}
EXPECTED_CANDIDATE_EXTERNAL_BLOCKERS = {
    "exact_commit": "not-authorized",
    "historical_tag_lineage": "blocked-pending-separate-release-authority",
    "signing": "not-authorized",
    "host_install_or_upgrade": "not-authorized",
    "publication": "not-authorized",
    "public_readback": "not-available",
}


def _read_json(path: Path, *, label: str) -> tuple[dict[str, Any], list[str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, [f"unable to read {label}: {exc}"]
    if not isinstance(payload, dict):
        return {}, [f"{label} must be a JSON object"]
    return payload, []


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    return completed.stdout.strip()


def source_snapshot() -> dict[str, Any]:
    """Hash every tracked or untracked source input except this self-bound report."""
    completed = subprocess.run(
        ["git", "ls-files", "-co", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        timeout=15,
    )
    paths = sorted(
        item.decode("utf-8")
        for item in completed.stdout.split(b"\0")
        if item and item.decode("utf-8") != CANDIDATE_RELATIVE
    )
    digest = hashlib.sha256()
    for relative in paths:
        path = ROOT / relative
        if not path.is_file():
            continue
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return {"sha256": digest.hexdigest(), "file_count": len(paths)}


def validate_candidate(
    payload: Mapping[str, Any],
    *,
    require_current_worktree: bool = False,
) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != 1 or payload.get("phase") != 6:
        errors.append("candidate evidence has an unsupported schema")
    if payload.get("release") != EXPECTED_RELEASE:
        errors.append("candidate evidence identifies the wrong release")
    if payload.get("status") != "local_ready_external_gates_open":
        errors.append("candidate evidence has the wrong readiness status")
    source = payload.get("source")
    if not isinstance(source, Mapping):
        return errors + ["candidate evidence lacks source identity"]
    head = source.get("head_commit")
    if not isinstance(head, str) or not EXPECTED_HEAD.fullmatch(head):
        errors.append("candidate evidence lacks a full Git HEAD")
    else:
        if require_current_worktree:
            try:
                current_head = _git("rev-parse", "HEAD")
            except (OSError, subprocess.SubprocessError) as exc:
                errors.append(f"unable to read current Git HEAD: {exc}")
            else:
                if head != current_head:
                    errors.append("candidate evidence Git HEAD differs from the checkout")
        if source.get("identity") != f"WORKTREE@{head}":
            errors.append("candidate source identity is not WORKTREE@HEAD")
    if source.get("exact_commit") is not False or source.get("worktree_clean") is not False:
        errors.append("dirty local candidate must not claim exact clean commit lineage")
    snapshot = source.get("snapshot")
    if not isinstance(snapshot, Mapping):
        errors.append("candidate evidence lacks its retained source snapshot")
    elif require_current_worktree and dict(snapshot) != source_snapshot():
        errors.append("candidate source snapshot differs from the current worktree")

    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list):
        return errors + ["candidate evidence lacks artifact records"]
    filenames = tuple(
        record.get("filename")
        for record in artifacts
        if isinstance(record, Mapping)
    )
    if filenames != EXPECTED_ARTIFACTS:
        errors.append("candidate artifact set differs from the five release artifacts")
    for record in artifacts:
        if not isinstance(record, Mapping):
            errors.append("candidate artifact record is malformed")
            continue
        digest = record.get("sha256")
        if not isinstance(digest, str) or not EXPECTED_DIGEST.fullmatch(digest):
            errors.append(f"{record.get('filename', 'artifact')} has an invalid digest")
        if record.get("verified") is not True:
            errors.append(f"{record.get('filename', 'artifact')} is not verified")

    evidence = payload.get("evidence")
    if not isinstance(evidence, Mapping):
        return errors + ["candidate evidence lacks verification results"]
    for field in (
        "checksums_verified",
        "sbom_verified",
        "provenance_verified",
        "rpm_headers_verified",
        "rpm_payload_digests_verified",
        "sdist_metadata_verified",
        "source_install_isolated_verified",
        "flatpak_import_verified",
    ):
        if evidence.get(field) is not True:
            errors.append(f"candidate evidence does not prove {field}")
    for field in (
        "exact_commit_verified",
        "rpm_signatures_verified",
        "host_install_verified",
        "host_upgrade_verified",
        "public_readback_verified",
    ):
        if evidence.get(field) is not False:
            errors.append(f"candidate evidence must keep {field} false")
    if payload.get("skipped_physical_gates") != EXPECTED_SKIPPED_GATES:
        errors.append("candidate evidence misstates the skipped physical gates")
    if payload.get("external_blockers") != EXPECTED_CANDIDATE_EXTERNAL_BLOCKERS:
        errors.append("candidate evidence misstates the external blockers")
    return errors


def validate_screenshots(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != 1 or payload.get("phase") != 6:
        errors.append("screenshot evidence has an unsupported schema")
    if payload.get("captured_product_version") != RETAINED_CANDIDATE_VERSION:
        errors.append("screenshot evidence did not capture v23.0.0")
    if payload.get("captured_product_codename") != EXPECTED_CODENAME:
        errors.append("screenshot evidence did not capture Compass")
    if payload.get("status") != "passed":
        errors.append("screenshot evidence is not passed")
    if payload.get("capture_policy", {}).get("physical_gate") != "not_verified":
        errors.append("offscreen screenshot evidence claims a physical gate")
    if len(payload.get("captures", [])) != 12:
        errors.append("screenshot evidence does not contain 12 frames")
    if len(payload.get("contact_sheets", [])) != 6:
        errors.append("screenshot evidence does not contain six contact sheets")
    return errors


def run_validation(
    candidate_path: Path = CANDIDATE,
    screenshot_path: Path = SCREENSHOTS,
) -> dict[str, Any]:
    candidate, candidate_read_errors = _read_json(candidate_path, label="candidate")
    screenshots, screenshot_read_errors = _read_json(
        screenshot_path, label="screenshots"
    )
    errors = (
        candidate_read_errors
        + screenshot_read_errors
        + validate_candidate(candidate)
        + validate_screenshots(screenshots)
    )
    return {
        "schema_version": 1,
        "release": EXPECTED_RELEASE,
        "source_snapshot": source_snapshot(),
        "status": "passed" if not errors else "failed",
        "errors": errors,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=CANDIDATE)
    parser.add_argument("--screenshots", type=Path, default=SCREENSHOTS)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    payload = run_validation(args.candidate, args.screenshots)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"[v23-phase6] {payload['status'].upper()}")
        print(f"- source files: {payload['source_snapshot']['file_count']}")
        print(f"- source SHA-256: {payload['source_snapshot']['sha256']}")
        for error in payload["errors"]:
            print(f"[v23-phase6] ERROR: {error}")
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
