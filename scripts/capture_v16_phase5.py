#!/usr/bin/env python3
"""Capture reproducible Standard-destination evidence for v16 Phase 5."""

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
OUTPUT_DIR = ROOT / "docs" / "images" / "v16" / "phase5"
REPORT_PATH = ROOT / "docs" / "reports" / "V16_PHASE5_SCREENSHOTS.json"
VIEWPORTS = ((860, 720), (1918, 1018))
ROUTES = (
    ("software-updates", "software:apps"),
    ("network-security", "network"),
    ("desktop", "desktop"),
    ("settings", "settings"),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _settle(app, cycles: int = 8) -> None:
    for _ in range(cycles):
        app.processEvents()


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, str(SRC))

    from PyQt6.QtCore import QCoreApplication, QEvent
    from PyQt6.QtWidgets import QApplication
    from core.navigation import NavigationMode
    from core.plugins.registry import PluginRegistry
    from ui.desktop_tab import DesktopTab
    from ui.main_window import MainWindow
    from ui.network_tab import NetworkTab
    from ui.software_tab import _ApplicationsSubTab
    from utils.command_runner import CommandRunner
    from utils.settings import SettingsManager

    app = QApplication.instance() or QApplication(["capture-v16-phase5"])
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []

    def reject_command(*_args, **_kwargs):
        raise RuntimeError("Phase 5 capture guard rejected an asynchronous command")

    with isolated_capture_home(), ExitStack() as stack:
        stack.enter_context(guarded_subprocesses())
        stack.enter_context(patch.object(MainWindow, "_check_first_run", lambda self: None))
        stack.enter_context(patch.object(MainWindow, "_initialize_background_services", lambda self: None))
        stack.enter_context(patch.object(MainWindow, "_schedule_post_render_services", lambda self: None))
        stack.enter_context(patch.object(CommandRunner, "run_command", reject_command))
        stack.enter_context(patch.object(_ApplicationsSubTab, "on_activate", lambda self: None))
        stack.enter_context(patch.object(NetworkTab, "_initial_load", lambda self: None))
        stack.enter_context(patch.object(DesktopTab, "_detect_displays", lambda self: None))
        stack.enter_context(patch.object(DesktopTab, "_load_session_info", lambda self: None))

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
        "phase": 5,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "capture_policy": {
            "real_main_window": True,
            "navigation_mode": "standard",
            "theme": "system",
            "backend": "offscreen",
            "temporary_home_and_xdg": True,
            "background_services_disabled": True,
            "mutating_subprocesses_rejected": True,
            "host_probes_disabled": True,
        },
        "reproduction_command": (
            "PYTHONPATH=loofi-fedora-tweaks QT_QPA_PLATFORM=offscreen "
            "python3 scripts/capture_v16_phase5.py"
        ),
        "captures": records,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"captured {len(records)} Phase 5 frames")
    print(REPORT_PATH.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
