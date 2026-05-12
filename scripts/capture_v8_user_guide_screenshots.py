#!/usr/bin/env python3
"""Capture current user-guide screenshots from the real PyQt application."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "loofi-fedora-tweaks"
OUT = ROOT / "docs" / "images" / "user-guide"

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(SRC))

from PyQt6.QtCore import QSize, Qt  # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QScrollArea  # noqa: E402

from ui.main_window import MainWindow  # noqa: E402
from ui.release_readiness_dialog import ReleaseReadinessDialog  # noqa: E402


WINDOW_SIZE = QSize(1400, 900)

ROUTE_SCREENSHOTS = [
    ("home-dashboard.png", ""),
    ("system-monitor.png", "system-monitor:processes"),
    ("maintenance-updates.png", "maintenance:updates"),
    ("network-overview.png", "network:connections"),
    ("security-privacy.png", "security:privacy"),
    ("settings-appearance.png", "settings:appearance"),
    ("ai-lab-models.png", "ai-lab:models"),
    ("community-presets.png", "community:presets"),
    ("community-marketplace.png", "community:marketplace"),
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


def _capture_main_window(app: QApplication) -> None:
    window = MainWindow()
    window.resize(WINDOW_SIZE)
    window.show()
    _settle(app, 1.5)

    for filename, route_id in ROUTE_SCREENSHOTS:
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
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")

    qss_path = SRC / "assets" / "modern.qss"
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))

    _capture_main_window(app)
    _capture_release_readiness(app)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
