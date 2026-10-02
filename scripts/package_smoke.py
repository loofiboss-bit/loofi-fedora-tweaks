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
        for command in ("info", "doctor"):
            try:
                result = subprocess.run(
                    [executable, "--cli", "--json", "--timeout", str(timeout), command],
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
    print(f"[package-smoke] OK: installed info {results['info']['version']}; doctor {doctor_state}; finite JSON contracts passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
