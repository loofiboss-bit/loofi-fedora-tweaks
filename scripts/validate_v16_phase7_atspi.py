#!/usr/bin/env python3
"""Smoke-test the live Loofi accessibility tree through AT-SPI."""

from __future__ import annotations

import argparse
import ast
import json
import os
import selectors
import subprocess
import sys
import time
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "loofi-fedora-tweaks"
REPORT_PATH = ROOT / "docs" / "reports" / "V16_PHASE7_ATSPI.json"
EXPECTED_SURFACES = {
    "application": ("Loofi Fedora Tweaks",),
    "navigation": (
        "Navigation destinations",
        "Primary navigation",
        "Sections",
    ),
    "page_title": ("System Information", "System information"),
    "result_state": ("Activity status",),
    "confirmation": ("Confirm action: Remove selected packages",),
}
ROUTE_SURFACES: dict[str, dict[str, tuple[str, ...]]] = {
    "diagnostics": {
        "page_title": ("Troubleshoot",),
        "troubleshoot_view": ("Troubleshoot view",),
        "troubleshoot_profile": ("Problem profile",),
        "troubleshoot_start": ("Start read-only check",),
    },
    "health": {
        "page_title": ("System Check",),
        "system_check_status": (
            "Latest saved check",
            "Refresh saved results",
        ),
    },
    "settings": {
        "page_title": ("Settings",),
        "settings_theme": ("Theme",),
        "settings_system_theme": ("System theme", "Follow system theme"),
        "settings_notifications": ("Notifications",),
    },
    "development": {
        "page_title": ("Development",),
        "specialist_filter": ("Filter specialist tools",),
        "specialist_group_filter": ("All groups",),
        "specialist_group_option": ("Development & local AI",),
    },
}


def _child() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "wayland")
    os.environ.setdefault("QT_LINUX_ACCESSIBILITY", "1")
    if str(SOURCE) not in sys.path:
        sys.path.insert(0, str(SOURCE))
    if str(ROOT / "scripts") not in sys.path:
        sys.path.insert(0, str(ROOT / "scripts"))

    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication
    from capture_v16_phase0 import guarded_subprocesses, isolated_capture_home
    from core.plugins.registry import PluginRegistry
    from ui.confirm_dialog import ConfirmActionDialog
    from ui.main_window import MainWindow
    from utils.command_runner import CommandRunner
    from utils.settings import SettingsManager

    application = QApplication(["loofi-v16-phase7-atspi"])

    def reject_command(*_args, **_kwargs):
        raise RuntimeError("AT-SPI smoke rejected an asynchronous command")

    with isolated_capture_home(), ExitStack() as stack:
        stack.enter_context(guarded_subprocesses())
        stack.enter_context(patch.object(MainWindow, "_check_first_run", lambda self: None))
        stack.enter_context(patch.object(MainWindow, "_initialize_background_services", lambda self: None))
        stack.enter_context(patch.object(MainWindow, "_schedule_post_render_services", lambda self: None))
        stack.enter_context(patch.object(CommandRunner, "run_command", reject_command))
        SettingsManager._reset_instance()
        PluginRegistry.reset()

        window = MainWindow()
        window.resize(1280, 720)
        window.show()
        route = os.environ.get("LOOFI_ATSPI_ROUTE", "system_info")
        if route == "development":
            from core.navigation import NavigationMode

            window._rebuild_sidebar_for_navigation_mode(
                NavigationMode.ADVANCED
            )
        window.switch_to_route(route)
        window.set_status("Validation completed")

        confirmation = ConfirmActionDialog(
            parent=window,
            action="Remove selected packages",
            description="Review the package list before continuing.",
            command_preview="dnf remove example",
            risk_level=ConfirmActionDialog.RISK_HIGH,
        )
        confirmation.show()
        QTimer.singleShot(500, lambda: print("READY", flush=True))
        QTimer.singleShot(20000, application.quit)
        result = application.exec()
        confirmation.close()
        window.close()
        return int(result)


def _walk(accessible: Any, *, depth: int = 0, limit: int = 20) -> list[dict[str, str]]:
    if depth > limit:
        return []
    try:
        name = str(accessible.name or "")
    except (AttributeError, RuntimeError):
        name = ""
    try:
        role = str(accessible.getRoleName() or "")
    except (AttributeError, RuntimeError):
        role = ""
    try:
        description = str(accessible.description or "")
    except (AttributeError, RuntimeError):
        description = ""
    records = [{"name": name, "role": role, "description": description}]
    try:
        children = list(accessible)
    except (RuntimeError, TypeError):
        children = []
    for child in children:
        records.extend(_walk(child, depth=depth + 1, limit=limit))
    return records


def _read_ready(process: subprocess.Popen[str], timeout: float = 12.0) -> tuple[bool, str]:
    if process.stdout is None:
        return False, "child stdout is unavailable"
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    deadline = time.monotonic() + timeout
    output: list[str] = []
    while time.monotonic() < deadline:
        events = selector.select(timeout=0.2)
        for key, _mask in events:
            line = key.fileobj.readline()
            if not line:
                continue
            output.append(line.rstrip())
            if line.strip() == "READY":
                selector.close()
                return True, "\n".join(output)
        if process.poll() is not None:
            break
    selector.close()
    return False, "\n".join(output)


def _session_atspi_address() -> str:
    try:
        completed = subprocess.run(
            [
                "gdbus",
                "call",
                "--session",
                "--dest",
                "org.a11y.Bus",
                "--object-path",
                "/org/a11y/bus",
                "--method",
                "org.a11y.Bus.GetAddress",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        result = ast.literal_eval(completed.stdout.strip())
        if completed.returncode == 0 and isinstance(result, tuple) and result:
            return str(result[0])
    except (FileNotFoundError, OSError, ValueError, SyntaxError, subprocess.SubprocessError):
        pass
    return ""


def run_probe(
    backend: str,
    *,
    route: str = "system_info",
    report_path: Path = REPORT_PATH,
    release: str = "v16.0.0 Clarity",
    phase: int = 7,
    retain_nodes: bool = True,
) -> dict[str, Any]:
    """Launch the real app and query its exported AT-SPI tree."""
    bus_address = _session_atspi_address()
    if bus_address:
        os.environ["AT_SPI_BUS_ADDRESS"] = bus_address
    try:
        import pyatspi
    except ImportError as exc:
        return {
            "status": "failed",
            "errors": [f"pyatspi is unavailable: {exc}"],
            "surfaces": {},
            "nodes": [],
        }

    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = backend
    environment["QT_LINUX_ACCESSIBILITY"] = "1"
    environment["PYTHONPATH"] = str(SOURCE)
    environment["LOOFI_ATSPI_ROUTE"] = route
    if bus_address:
        environment["AT_SPI_BUS_ADDRESS"] = bus_address
    process = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "--child"],
        cwd=ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    ready, child_output = _read_ready(process)
    nodes: list[dict[str, str]] = []
    errors: list[str] = []
    try:
        if not ready:
            errors.append("real MainWindow did not become ready for AT-SPI inspection")
        else:
            deadline = time.monotonic() + 8.0
            while time.monotonic() < deadline and not nodes:
                desktop = pyatspi.Registry.getDesktop(0)
                for application in desktop:
                    application_nodes = _walk(application)
                    if any("Loofi Fedora Tweaks" in node["name"] for node in application_nodes):
                        nodes = application_nodes
                        break
                if not nodes:
                    time.sleep(0.2)
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    names = {node["name"] for node in nodes if node["name"]}
    surfaces: dict[str, dict[str, Any]] = {}
    expected_surfaces = dict(EXPECTED_SURFACES)
    expected_surfaces.update(ROUTE_SURFACES.get(route, {}))
    for surface, candidates in expected_surfaces.items():
        matches = sorted(
            name
            for name in names
            if any(candidate.casefold() in name.casefold() for candidate in candidates)
        )
        surfaces[surface] = {
            "expected": list(candidates),
            "matches": matches,
            "status": "passed" if matches else "failed",
        }
        if not matches:
            errors.append(f"AT-SPI surface was not exposed: {surface}")

    payload = {
        "schema_version": 1,
        "release": release,
        "phase": phase,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "backend": backend,
        "protocol": "AT-SPI2",
        "bus_address_resolved": bool(bus_address),
        "real_main_window": True,
        "route": route,
        "orca_available": bool(shutil_which("orca")),
        "child_output": child_output,
        "surfaces": surfaces,
        "node_count": len(nodes),
        "nodes_retained": retain_nodes,
        "nodes": nodes if retain_nodes else [],
        "status": "passed" if not errors else "failed",
        "errors": errors,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def shutil_which(program: str) -> str:
    """Resolve a program without importing application utilities."""
    from shutil import which

    return which(program) or ""


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--backend", choices=("wayland", "xcb"), default="wayland")
    parser.add_argument("--route", default="system_info")
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    parser.add_argument("--release", default="v16.0.0 Clarity")
    parser.add_argument("--phase", type=int, default=7)
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="validate the live tree but omit raw nodes from the saved report",
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.child:
        return _child()
    payload = run_probe(
        args.backend,
        route=args.route,
        report_path=args.report,
        release=args.release,
        phase=args.phase,
        retain_nodes=not args.summary_only,
    )
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"v16 Phase 7 AT-SPI validation: {payload['status']}")
        try:
            print(str(args.report.relative_to(ROOT)))
        except ValueError:
            print(str(args.report))
        for error in payload["errors"]:
            print(f"- {error}")
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
