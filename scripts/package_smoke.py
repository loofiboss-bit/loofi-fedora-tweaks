#!/usr/bin/env python3
"""Validate installed CLI inspection contracts as a disposable regular user.

XDG application state and Python import paths are isolated. The installed
launcher still writes its startup log under the user's home, so run this in
the package-test container with a disposable user, never as root.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

INFO_FIELDS = {"version", "codename", "system_type", "package_manager", "power_profile"}
DOCTOR_STRING_FIELDS = {"support_status", "deployment_backend", "desktop", "session_type", "reboot_status"}
DOCTOR_BOOL_FIELDS = {"platform_ok", "profile_error", "polkit_active", "all_critical_ok"}
DOCTOR_FIELDS = DOCTOR_STRING_FIELDS | DOCTOR_BOOL_FIELDS | {"fedora_version", "reboot_pending", "critical", "optional"}
GUIDE_LIST_FIELDS = {"schema_id", "schema_version", "active_guide", "writable", "reason_code", "guides"}
GUIDE_FIELDS = {
    "schema_id", "schema_version", "progress_revision", "id", "title", "description",
    "steps", "active", "writable", "reason_code",
}
PROFILE_LIBRARY_FIELDS = {"schema", "profiles"}
PRESET_FIELDS = {"schema", "presets"}


def _validate_finite(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("JSON contains a non-finite number.")
    if isinstance(value, dict):
        for item in value.values():
            _validate_finite(item)
    elif isinstance(value, list):
        for item in value:
            _validate_finite(item)


def validate_payload(command: str, stdout: str, returncode: int) -> dict[str, Any]:
    """Require one finite JSON object with the maintained inspection shape."""
    try:
        payload = json.loads(stdout)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{command}: output is not one valid JSON response (exit {returncode}).") from exc
    _validate_finite(payload)
    if not isinstance(payload, dict):
        raise ValueError(f"{command}: JSON response must be an object.")
    if command == "info":
        expected = INFO_FIELDS | ({"pending_deployment"} if payload.get("system_type") == "Atomic" else set())
        if set(payload) != expected or not all(isinstance(payload.get(key), str) for key in INFO_FIELDS):
            raise ValueError("info: inspection JSON fields or types changed.")
        if payload["system_type"] not in {"Traditional", "Atomic"} or not payload["version"]:
            raise ValueError("info: system type or package version is invalid.")
        pending = payload.get("pending_deployment")
        if pending is not None and type(pending) is not bool:
            raise ValueError("info: pending deployment must be boolean or null.")
        if returncode != 0:
            raise ValueError(f"info: inspection failed with exit {returncode}.")
    elif command == "doctor":
        if set(payload) != DOCTOR_FIELDS:
            raise ValueError("doctor: inspection JSON fields changed.")
        if not all(isinstance(payload[key], str) for key in DOCTOR_STRING_FIELDS) or not all(type(payload[key]) is bool for key in DOCTOR_BOOL_FIELDS):
            raise ValueError("doctor: inspection JSON field types changed.")
        if payload["fedora_version"] is not None and type(payload["fedora_version"]) is not int:
            raise ValueError("doctor: Fedora version must be an integer or null.")
        if payload["reboot_pending"] is not None and type(payload["reboot_pending"]) is not bool:
            raise ValueError("doctor: reboot state must be boolean or null.")
        for name in ("critical", "optional"):
            tools = payload[name]
            if not isinstance(tools, dict) or not tools or not all(type(value) is bool for value in tools.values()):
                raise ValueError(f"doctor: {name} tool availability must be a boolean mapping.")
        expected_exit = 0 if payload["all_critical_ok"] else 1
        if returncode != expected_exit:
            raise ValueError(f"doctor: exit {returncode} contradicts the reported availability.")
    elif command == "guides list":
        if set(payload) != GUIDE_LIST_FIELDS:
            raise ValueError("guides list: inspection JSON fields changed.")
        if payload["schema_id"] != "loofi.user-guides" or payload["schema_version"] != 1:
            raise ValueError("guides list: progress schema changed.")
        if not isinstance(payload["active_guide"], str) or type(payload["writable"]) is not bool or not isinstance(payload["reason_code"], str):
            raise ValueError("guides list: progress field types changed.")
        guides = payload["guides"]
        if not isinstance(guides, list) or not guides:
            raise ValueError("guides list: the curated guide catalog is empty.")
        for guide in guides:
            if not isinstance(guide, dict) or set(guide) != {"id", "title", "active", "completed_steps", "step_count"}:
                raise ValueError("guides list: guide summary fields changed.")
            if not all(isinstance(guide[key], str) for key in ("id", "title")) or type(guide["active"]) is not bool:
                raise ValueError("guides list: guide summary types changed.")
            if type(guide["completed_steps"]) is not int or type(guide["step_count"]) is not int or guide["step_count"] <= 0:
                raise ValueError("guides list: step counts must be positive integers.")
        if returncode != 0:
            raise ValueError(f"guides list: inspection failed with exit {returncode}.")
    elif command.startswith("guides show "):
        if set(payload) != GUIDE_FIELDS:
            raise ValueError("guides show: inspection JSON fields changed.")
        if payload["schema_id"] != "loofi.user-guide" or payload["schema_version"] != 1:
            raise ValueError("guides show: guide response schema changed.")
        if not isinstance(payload["id"], str) or not isinstance(payload["title"], str) or not isinstance(payload["description"], str):
            raise ValueError("guides show: guide identity types changed.")
        if type(payload["progress_revision"]) is not int or type(payload["active"]) is not bool or type(payload["writable"]) is not bool or not isinstance(payload["reason_code"], str):
            raise ValueError("guides show: progress field types changed.")
        steps = payload["steps"]
        if not isinstance(steps, list) or not steps:
            raise ValueError("guides show: the guide has no steps.")
        step_fields = {
            "id", "title", "description", "target", "keywords", "evidence_kinds", "status",
            "updated_at", "evidence_kind", "evidence_id", "evidence_available",
        }
        for step in steps:
            if not isinstance(step, dict) or set(step) != step_fields:
                raise ValueError("guides show: step fields changed.")
            if not all(isinstance(step[key], str) for key in ("id", "title", "description", "status", "evidence_kind", "evidence_id")):
                raise ValueError("guides show: step text fields changed.")
            if step["status"] not in {"not_started", "in_progress", "reviewed", "skipped", "verified", "evidence_missing"}:
                raise ValueError("guides show: unsupported progress state.")
            if not isinstance(step["keywords"], list) or not all(isinstance(item, str) for item in step["keywords"]):
                raise ValueError("guides show: keywords must be strings.")
            if not isinstance(step["evidence_kinds"], list) or not all(isinstance(item, str) for item in step["evidence_kinds"]):
                raise ValueError("guides show: evidence kinds must be strings.")
            if type(step["evidence_available"]) is not bool:
                raise ValueError("guides show: evidence availability must be boolean.")
            if step["updated_at"] is not None and (isinstance(step["updated_at"], bool) or not isinstance(step["updated_at"], (int, float))):
                raise ValueError("guides show: update time must be numeric or null.")
            target = step["target"]
            if not isinstance(target, dict) or set(target) != {"route_id", "task_id", "tweak_id", "context"}:
                raise ValueError("guides show: navigation target fields changed.")
            if not all(isinstance(target[key], str) for key in ("route_id", "task_id", "tweak_id")) or not isinstance(target["context"], dict):
                raise ValueError("guides show: navigation target types changed.")
        if returncode != 0:
            raise ValueError(f"guides show: inspection failed with exit {returncode}.")
    elif command == "tweaks profile library list":
        if set(payload) != PROFILE_LIBRARY_FIELDS or payload["schema"] != "loofi.tweak-library/v1":
            raise ValueError("tweaks profile library list: library schema changed.")
        profiles = payload["profiles"]
        # Built-in profiles are desktop-specific. A headless package-validation
        # container has no supported desktop, so an empty library is valid; the
        # separate preset-list contract below verifies the static catalog.
        if not isinstance(profiles, list):
            raise ValueError("tweaks profile library list: profiles must be an array.")
        for entry in profiles:
            if not isinstance(entry, dict) or set(entry) != {"id", "builtin", "description", "profile"}:
                raise ValueError("tweaks profile library list: entry fields changed.")
            profile = entry["profile"]
            if not isinstance(entry["id"], str) or type(entry["builtin"]) is not bool or not isinstance(entry["description"], str):
                raise ValueError("tweaks profile library list: entry types changed.")
            if not isinstance(profile, dict) or set(profile) != {"schema", "name", "desktop", "settings"}:
                raise ValueError("tweaks profile library list: profile fields changed.")
            if profile["schema"] != "loofi.tweak-profile/v1" or not all(isinstance(profile[key], str) for key in ("name", "desktop")):
                raise ValueError("tweaks profile library list: profile schema or types changed.")
            settings = profile["settings"]
            if not isinstance(settings, list) or not all(isinstance(item, dict) and set(item) == {"id", "value"} and all(isinstance(item[key], str) for key in ("id", "value")) for item in settings):
                raise ValueError("tweaks profile library list: setting fields changed.")
        if returncode != 0:
            raise ValueError(f"tweaks profile library list: inspection failed with exit {returncode}.")
    elif command == "tweaks preset list":
        if set(payload) != PRESET_FIELDS or payload["schema"] != "loofi.tweak-presets/v1":
            raise ValueError("tweaks preset list: preset schema changed.")
        presets = payload["presets"]
        if not isinstance(presets, list) or not presets:
            raise ValueError("tweaks preset list: the preset catalog is empty.")
        for preset in presets:
            if not isinstance(preset, dict) or set(preset) != {"id", "name", "description", "desktops"}:
                raise ValueError("tweaks preset list: preset fields changed.")
            if not all(isinstance(preset[key], str) for key in ("id", "name", "description")):
                raise ValueError("tweaks preset list: preset text fields changed.")
            if not isinstance(preset["desktops"], list) or not all(isinstance(item, str) for item in preset["desktops"]):
                raise ValueError("tweaks preset list: desktop targets must be strings.")
        if returncode != 0:
            raise ValueError(f"tweaks preset list: inspection failed with exit {returncode}.")
    else:
        raise ValueError(f"Unsupported inspection command: {command}")
    return payload


def run_smoke(launcher: str, timeout: int = 60) -> dict[str, dict[str, Any]]:
    """Inspect the installed launcher, without importing checkout modules."""
    if timeout <= 0:
        raise ValueError("The inspection timeout must be positive.")
    executable = shutil.which(launcher)
    if executable is None:
        raise ValueError("The installed application launcher was not found.")
    results: dict[str, dict[str, Any]] = {}
    with tempfile.TemporaryDirectory(prefix="loofi-package-smoke-") as directory:
        root = Path(directory)
        environment = os.environ.copy()
        for name in ("PYTHONPATH", "PYTHONHOME", "DBUS_SESSION_BUS_ADDRESS"):
            environment.pop(name, None)
        environment["PYTHONNOUSERSITE"] = "1"
        for variable, name in (
            ("XDG_CONFIG_HOME", "config"), ("XDG_DATA_HOME", "data"),
            ("XDG_CACHE_HOME", "cache"), ("XDG_STATE_HOME", "state"),
            ("XDG_RUNTIME_DIR", "runtime"),
        ):
            path = root / name
            path.mkdir(mode=0o700)
            environment[variable] = str(path)
        commands = (
            ("info", ("info",)),
            ("doctor", ("doctor",)),
            ("guides list", ("guides", "list")),
            ("guides show make-fedora-yours", ("guides", "show", "make-fedora-yours")),
            ("tweaks profile library list", ("tweaks", "profile", "library", "list")),
            ("tweaks preset list", ("tweaks", "preset", "list")),
        )
        for command, arguments in commands:
            try:
                result = subprocess.run(
                    [executable, "--cli", "--json", "--timeout", str(timeout), *arguments],
                    cwd=root, env=environment, capture_output=True, text=True,
                    check=False, timeout=timeout,
                )
            except subprocess.TimeoutExpired as exc:
                raise ValueError(f"{command}: installed CLI inspection timed out.") from exc
            except OSError as exc:
                raise ValueError(f"{command}: installed CLI inspection could not start.") from exc
            results[command] = validate_payload(command, result.stdout, result.returncode)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launcher", default="loofi-fedora-tweaks", help="Installed application launcher.")
    parser.add_argument("--timeout", type=int, default=60, help="Bounded seconds per inspection command.")
    args = parser.parse_args(argv)
    try:
        results = run_smoke(args.launcher, args.timeout)
    except (OSError, ValueError) as exc:
        print(f"[package-smoke] ERROR: {exc}", file=sys.stderr)
        return 1
    doctor_state = "healthy" if results["doctor"]["all_critical_ok"] else "unavailable"
    print(f"[package-smoke] OK: installed info {results['info']['version']}; doctor {doctor_state}; read-only guide, preset, and profile lists; finite JSON contracts passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
