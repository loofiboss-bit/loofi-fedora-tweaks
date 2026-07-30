#!/usr/bin/env python3
"""Capture current user-guide screenshots from the real PyQt application."""

from __future__ import annotations

import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "loofi-fedora-tweaks"
OUT = ROOT / "docs" / "images" / "user-guide"

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(SRC))

from PyQt6.QtCore import QSize, Qt  # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QScrollArea  # noqa: E402
from ui.design import ThemeManager  # noqa: E402


WINDOW_SIZE = QSize(1400, 900)

ROUTE_SCREENSHOTS = [
    ("home-dashboard.png", "", False),
    ("upgrade-assistant.png", "maintenance:upgrade-assistant", False),
    ("system-monitor.png", "system-monitor:processes", False),
    ("maintenance-updates.png", "maintenance:updates", False),
    ("network-overview.png", "network:connections", False),
    ("security-privacy.png", "security:privacy", False),
    ("settings-appearance.png", "settings:appearance", False),
    ("ai-lab-models.png", "ai-lab:models", True),
    ("community-legacy-extensions.png", "community:presets", True),
]


def _settle(app: QApplication, seconds: float = 0.75) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.02)


def _save_widget(widget, filename: str) -> None:
    path = OUT / filename
    pixmap = widget.grab()
    if pixmap.isNull() or not pixmap.save(str(path), "PNG"):
        raise RuntimeError(f"failed to save {path}")
    print(f"captured {path.relative_to(ROOT)}")


@contextmanager
def _screenshot_home() -> Iterator[None]:
    """Use a deterministic profile so captures do not depend on local user state."""
    if os.environ.get("LOOFI_SCREENSHOT_REAL_HOME") == "1":
        yield
        return

    original_home = os.environ.get("HOME")
    with TemporaryDirectory(prefix="loofi-screenshots-") as tmp_home:
        os.environ["HOME"] = tmp_home
        config_dir = Path(tmp_home) / ".config" / "loofi-fedora-tweaks"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "first_run_complete").touch()
        (config_dir / "tour_complete").touch()
        (config_dir / "favorites.json").write_text('{"version": 2, "favorites": []}\n', encoding="utf-8")
        (config_dir / "settings.json").write_text(
            (
                "{\n"
                '  "theme": "dark",\n'
                '  "follow_system_theme": false,\n'
                '  "navigation_mode": "standard",\n'
                '  "restore_last_tab": false,\n'
                '  "last_tab_index": 0\n'
                "}\n"
            ),
            encoding="utf-8",
        )
        try:
            yield
        finally:
            if original_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = original_home


def _capture_main_window(app: QApplication) -> None:
    from core.navigation.models import NavigationMode
    from ui.main_window import MainWindow

    window = MainWindow()
    window.resize(WINDOW_SIZE)
    window.show()
    _settle(app, 1.5)

    advanced_enabled = False
    for filename, route_id, requires_advanced in ROUTE_SCREENSHOTS:
        if requires_advanced and not advanced_enabled:
            window.apply_navigation_mode(NavigationMode.ADVANCED)
            advanced_enabled = True
            _settle(app, 0.5)
        if route_id and not window.switch_to_route(route_id):
            raise RuntimeError(f"route did not resolve in MainWindow: {route_id}")
        _settle(app, 1.0)
        _save_widget(window, filename)

    window.close()
    _settle(app, 0.2)


def _wait_for_readiness(dialog: ReleaseReadinessDialog, app: QApplication, timeout: float = 45.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if dialog.report is not None:
            return
        time.sleep(0.05)
    raise TimeoutError("release readiness report did not finish in time")


def _capture_release_readiness(app: QApplication) -> None:
    from ui.release_readiness_dialog import ReleaseReadinessDialog

    dialog = ReleaseReadinessDialog(auto_run=True)
    dialog.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
    dialog.resize(QSize(1100, 820))
    dialog.show()
    _wait_for_readiness(dialog, app)
    _settle(app, 0.5)
    _save_widget(dialog, "release-readiness.png")

    dialog.advanced_toggle.setChecked(True)
    attention_index = dialog.severity_filter.findData("attention")
    if attention_index >= 0:
        dialog.severity_filter.setCurrentIndex(attention_index)
    dialog.resize(QSize(1100, 620))
    _settle(app, 0.5)
    scroll_area = dialog.findChild(QScrollArea)
    if scroll_area is not None:
        scroll_area.verticalScrollBar().setValue(0)
    _save_widget(dialog, "release-readiness-advanced.png")

    dialog.done(QDialog.DialogCode.Accepted)
    _settle(app, 0.2)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with _screenshot_home():
        app = QApplication.instance() or QApplication(sys.argv)
        app.setStyle("Fusion")

        if not ThemeManager().apply(app, "dark"):
            raise RuntimeError("failed to apply the semantic dark theme")

        _capture_main_window(app)
        _capture_release_readiness(app)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
