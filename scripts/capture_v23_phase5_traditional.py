#!/usr/bin/env python3
"""Capture fresh bounded troubleshooting evidence on Fedora 44 Traditional."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "loofi-fedora-tweaks"
MAIN = SOURCE / "main.py"
REPORT_PATH = ROOT / "docs" / "reports" / "V23_PHASE5_TRADITIONAL_PROFILES.json"
TERMINAL_STATES = {"completed", "partial"}
APPLICATION_ID = "firefox"

if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

from core.troubleshooting.profiles import all_profiles  # noqa: E402


def _run(
    command: Sequence[str],
    *,
    env: Mapping[str, str] | None = None,
    timeout: float = 30.0,
    accepted_codes: frozenset[int] = frozenset({0}),
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        list(command),
        cwd=ROOT,
        env=dict(env) if env is not None else None,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if completed.returncode not in accepted_codes:
        raise RuntimeError(
            f"{Path(command[0]).name} exited with {completed.returncode}"
        )
    return completed


def _os_release() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key] = value.strip().strip('"')
    return values


def _git_head() -> str:
    return _run(("git", "rev-parse", "HEAD"), timeout=10).stdout.strip()


def _host_record() -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    release = _os_release()
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "")
    virtualization = _run(
        ("systemd-detect-virt",),
        timeout=10,
        accepted_codes=frozenset({0, 1}),
    ).stdout.strip() or "unknown"
    rpm_ostree = _run(
        ("rpm-ostree", "status"),
        timeout=15,
        accepted_codes=frozenset({0, 1}),
    )
    atomic = rpm_ostree.returncode == 0

    if release.get("ID") != "fedora" or release.get("VERSION_ID") != "44":
        errors.append("host is not Fedora 44")
    if release.get("VARIANT_ID") != "kde":
        errors.append("host is not Fedora KDE")
    if session_type != "wayland":
        errors.append("host session is not Wayland")
    if atomic:
        errors.append("host is Atomic rather than Traditional")
    if virtualization != "none":
        errors.append("systemd-detect-virt did not identify a physical host")

    return {
        "os_id": release.get("ID", ""),
        "version_id": release.get("VERSION_ID", ""),
        "variant_id": release.get("VARIANT_ID", ""),
        "session_type": session_type,
        "desktop": desktop,
        "package_model": "atomic" if atomic else "traditional",
        "virtualization": virtualization,
    }, errors


def _profile_source_ids(profile_id: str) -> tuple[str, ...]:
    for profile in all_profiles():
        if profile.id == profile_id:
            return tuple(
                sorted(
                    budget.source_id
                    for budget in profile.source_budgets
                    if "traditional" in budget.variants
                )
            )
    raise LookupError(f"unknown profile: {profile_id}")


def _run_profile(
    profile_id: str,
    *,
    environment: Mapping[str, str],
    timeout_seconds: float,
) -> tuple[dict[str, Any], list[str]]:
    command = [
        sys.executable,
        str(MAIN),
        "--cli",
        "--json",
        "troubleshoot",
        "run",
        profile_id,
    ]
    if profile_id == "application_failed":
        command.extend(("--application-id", APPLICATION_ID))

    started = time.monotonic()
    completed = _run(
        command,
        env=environment,
        timeout=timeout_seconds + 30.0,
        accepted_codes=frozenset({0, 1}),
    )
    elapsed = time.monotonic() - started
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"{profile_id} did not emit one JSON envelope"
        ) from exc

    data = payload.get("data", {})
    session = data.get("session", {})
    source_results = session.get("source_results", [])
    actual_sources = tuple(
        sorted(
            str(item.get("source_id", ""))
            for item in source_results
            if isinstance(item, Mapping)
        )
    )
    expected_sources = _profile_source_ids(profile_id)
    state = str(session.get("state", ""))
    errors: list[str] = []
    if payload.get("schema_id") != "loofi.troubleshooting":
        errors.append(f"{profile_id} emitted an unexpected interface schema")
    if payload.get("command") != "run":
        errors.append(f"{profile_id} emitted an unexpected command")
    if session.get("profile_id") != profile_id:
        errors.append(f"{profile_id} emitted the wrong profile identity")
    if session.get("variant") != "traditional":
        errors.append(f"{profile_id} did not retain Traditional identity")
    if state not in TERMINAL_STATES or completed.returncode != 0:
        errors.append(f"{profile_id} did not reach a successful terminal state")
    if actual_sources != expected_sources:
        errors.append(f"{profile_id} source projection differs from its budget")

    state_counts: dict[str, int] = {}
    for item in source_results:
        source_state = str(item.get("state", "unknown"))
        state_counts[source_state] = state_counts.get(source_state, 0) + 1

    return {
        "profile_id": profile_id,
        "variant": session.get("variant"),
        "state": state,
        "elapsed_seconds": round(elapsed, 3),
        "budget_seconds": timeout_seconds,
        "source_ids": list(actual_sources),
        "source_state_counts": state_counts,
        "finding_count": len(session.get("findings", [])),
        "related_change_count": len(session.get("related_changes", [])),
        "persistence_warning": str(data.get("persistence_warning", "")),
    }, errors


def capture() -> dict[str, Any]:
    host, errors = _host_record()
    profile_records: list[dict[str, Any]] = []
    profiles = all_profiles()
    with tempfile.TemporaryDirectory(
        prefix="loofi-v23-phase5-traditional-"
    ) as temporary_root:
        root = Path(temporary_root)
        environment = dict(os.environ)
        environment.update(
            {
                "PYTHONPATH": str(SOURCE),
                "XDG_CONFIG_HOME": str(root / "config"),
                "XDG_DATA_HOME": str(root / "data"),
                "XDG_CACHE_HOME": str(root / "cache"),
                "XDG_RUNTIME_DIR": str(root / "runtime"),
            }
        )
        for profile in profiles:
            record, profile_errors = _run_profile(
                profile.id,
                environment=environment,
                timeout_seconds=profile.total_budget_seconds,
            )
            profile_records.append(record)
            errors.extend(profile_errors)

    payload: dict[str, Any] = {
        "schema_version": 1,
        "release": "v23.0.0 Compass working tree",
        "product_metadata": "v22.0.0 Alignment",
        "phase": 5,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_identity": f"WORKTREE@{_git_head()}",
        "host": host,
        "capture_policy": {
            "explicit_cli_collection": True,
            "isolated_xdg_state": True,
            "mutating_actions": False,
            "raw_cli_payloads_retained": False,
            "profile_parameters": {
                "application_failed": {"application_id": APPLICATION_ID},
            },
        },
        "profiles": profile_records,
        "status": "passed" if not errors else "failed",
        "errors": errors,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def validate_report() -> list[str]:
    try:
        payload = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"Traditional profile evidence is unreadable: {exc}"]

    errors: list[str] = []
    if payload.get("schema_version") != 1 or payload.get("phase") != 5:
        errors.append("Traditional profile evidence has an unsupported schema")
    if payload.get("status") != "passed" or payload.get("errors") != []:
        errors.append("Traditional profile evidence is not a passed result")
    host = payload.get("host", {})
    expected_host = {
        "os_id": "fedora",
        "version_id": "44",
        "variant_id": "kde",
        "session_type": "wayland",
        "package_model": "traditional",
        "virtualization": "none",
    }
    if any(host.get(key) != value for key, value in expected_host.items()):
        errors.append("Traditional profile host identity differs from Fedora 44 KDE")

    records = payload.get("profiles", [])
    expected_ids = tuple(profile.id for profile in all_profiles())
    actual_ids = tuple(
        record.get("profile_id")
        for record in records
        if isinstance(record, Mapping)
    )
    if actual_ids != expected_ids:
        errors.append("Traditional profile evidence does not cover the closed catalog")
    for record in records:
        if not isinstance(record, Mapping):
            errors.append("Traditional profile evidence contains a malformed record")
            continue
        profile_id = str(record.get("profile_id", ""))
        if record.get("variant") != "traditional":
            errors.append(f"{profile_id} lost Traditional identity")
        if record.get("state") not in TERMINAL_STATES:
            errors.append(f"{profile_id} is not terminal")
        if tuple(record.get("source_ids", [])) != _profile_source_ids(profile_id):
            errors.append(f"{profile_id} source projection drifted")
    return errors


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate the retained Traditional profile evidence",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.check:
        errors = validate_report()
        for error in errors:
            print(f"[v23-phase5-traditional] ERROR: {error}")
        if not errors:
            print("[v23-phase5-traditional] PASSED: six profiles")
        return 1 if errors else 0

    payload = capture()
    for record in payload["profiles"]:
        print(
            f"{record['profile_id']}: {record['state']} "
            f"({record['elapsed_seconds']:.3f}s)"
        )
    print(f"[v23-phase5-traditional] {payload['status'].upper()}")
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
