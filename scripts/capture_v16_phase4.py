#!/usr/bin/env python3
"""Capture reproducible Home and System evidence for v16 Phase 4."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from capture_v16_phase0 import guarded_subprocesses, isolated_capture_home


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "loofi-fedora-tweaks"
OUTPUT_DIR = ROOT / "docs" / "images" / "v16" / "phase4"
REPORT_PATH = ROOT / "docs" / "reports" / "V16_PHASE4_SCREENSHOTS.json"
VIEWPORTS = ((860, 720), (1918, 1018))
ROUTES = (("home", "atlas_dashboard"), ("system-info", "system_info"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _settle(app, cycles: int = 8) -> None:
    for _ in range(cycles):
        app.processEvents()


def _home_summary():
    from core.home import (
        AttentionItem,
        HomeStatus,
        HomeSummary,
        HomeTask,
        Recommendation,
    )

    return HomeSummary(
        overall_state="attention",
        data_state="fresh",
        summary="Your system is stable. One update is worth reviewing.",
        generated_at=datetime.now(timezone.utc),
        primary_recommendation=Recommendation(
            id="updates",
            kind="updates",
            title="Review available updates",
            summary="Security and reliability updates are ready for review.",
            route_id="software:updates",
        ),
        attention_items=(
            AttentionItem(
                id="storage",
                title="Storage needs a quick look",
                summary="The main filesystem has less free space than usual.",
                route_id="storage",
                severity="attention",
            ),
        ),
        common_tasks=(
            HomeTask("updates", "Update software", "Review system and app updates.", "software:updates", "software-updates"),
            HomeTask("health", "Check system health", "Review health signals and history.", "system-health", "health"),
            HomeTask("storage", "Manage storage", "Inspect disks and free space.", "storage", "drive-harddisk"),
            HomeTask("recovery", "Open recovery", "Manage snapshots and recovery options.", "snapshots", "backup"),
        ),
        recent_change=None,
        status_items=(
            HomeStatus("health", "Health", "good", "No current health warnings", "system-health"),
            HomeStatus("updates", "Updates", "attention", "Updates are ready to review", "software:updates"),
            HomeStatus("storage", "Storage", "attention", "Free space is running lower", "storage"),
            HomeStatus("recovery", "Recovery", "good", "A recent snapshot is available", "snapshots"),
        ),
    )


def _fill_system_info(tab) -> None:
    values = {
        "hostname": "clarity-workstation",
        "fedora": "Fedora Linux 44 (KDE Plasma)",
        "kernel": "6.15.8-300.fc44.x86_64",
        "cpu": "AMD Ryzen 7 7840U with Radeon 780M Graphics",
        "ram": "7.8 GiB / 31.1 GiB",
        "disk": "212 GiB free / 476 GiB",
        "uptime": "3 hours, 18 minutes",
        "battery": "Charging, 84%",
    }
    for key, value in values.items():
        row = tab.definition_rows[key]
        row.set_value(value)
        row.copy_button.setEnabled(True)


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, str(SRC))

    from PyQt6.QtCore import QCoreApplication, QEvent
    from PyQt6.QtWidgets import QApplication
    from core.home.service import HomeService
    from core.navigation import NavigationMode
    from core.plugins.registry import PluginRegistry
    from ui.main_window import MainWindow
    from ui.system_info_tab import SystemInfoTab
    from utils.command_runner import CommandRunner
    from utils.settings import SettingsManager

    app = QApplication.instance() or QApplication(["capture-v16-phase4"])
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []

    def reject_command(*_args, **_kwargs):
        raise RuntimeError("Phase 4 capture guard rejected an asynchronous command")

    with isolated_capture_home(), ExitStack() as stack:
        stack.enter_context(guarded_subprocesses())
        stack.enter_context(patch.object(MainWindow, "_check_first_run", lambda self: None))
        stack.enter_context(patch.object(MainWindow, "_initialize_background_services", lambda self: None))
        stack.enter_context(patch.object(MainWindow, "_schedule_post_render_services", lambda self: None))
        stack.enter_context(patch.object(CommandRunner, "run_command", reject_command))
        stack.enter_context(patch.object(HomeService, "summary", return_value=_home_summary()))
        stack.enter_context(patch.object(SystemInfoTab, "refresh_info", _fill_system_info))

        for width, height in VIEWPORTS:
            SettingsManager._reset_instance()
            PluginRegistry.reset()
            window = MainWindow()
            window.apply_navigation_mode(NavigationMode.STANDARD)
            window.resize(width, height)
            window.show()
            _settle(app)
            try:
                for destination, route_id in ROUTES:
                    if not window.switch_to_route(route_id):
                        raise RuntimeError(f"route did not resolve: {route_id}")
                    _settle(app)
                    output = OUTPUT_DIR / f"{destination}__{width}x{height}.png"
                    pixmap = window.grab()
                    if pixmap.isNull() or not pixmap.save(str(output), "PNG"):
                        raise RuntimeError(f"failed to save capture: {output}")
                    records.append(
                        {
                            "path": str(output.relative_to(ROOT)),
                            "sha256": _sha256(output),
                            "destination": destination,
                            "route_id": route_id,
                            "viewport": [width, height],
                            "captured_dimensions": [pixmap.width(), pixmap.height()],
                        }
                    )
            finally:
                window.deleteLater()
                QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                _settle(app, 2)

    manifest = {
        "schema_version": 1,
        "release": "v16.0.0 Clarity",
        "phase": 4,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "capture_policy": {
            "real_main_window": True,
            "navigation_mode": "standard",
            "theme": "system",
            "backend": "offscreen",
            "temporary_home_and_xdg": True,
            "background_services_disabled": True,
            "mutating_subprocesses_rejected": True,
            "deterministic_home_and_system_data": True,
        },
        "reproduction_command": (
            "PYTHONPATH=loofi-fedora-tweaks QT_QPA_PLATFORM=offscreen "
            "python3 scripts/capture_v16_phase4.py"
        ),
        "captures": records,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"captured {len(records)} Phase 4 frames")
    print(REPORT_PATH.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
