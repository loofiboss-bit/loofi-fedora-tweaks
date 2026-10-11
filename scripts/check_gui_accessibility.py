#!/usr/bin/env python3
"""Exercise the real review dialog at several Qt scales, themes and text sizes.

This fixture never reads or changes desktop settings. Native-platform runs
briefly show a review dialog; they do not drive another application's input.
Human screen-reader usability and hardware behavior require separate evidence.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def check_case(theme: str, point_size: int, screenshot: Path | None = None) -> dict[str, object]:
    from PyQt6.QtCore import QPoint, Qt
    from PyQt6.QtGui import QFont
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication, QDialog
    from ui.confirm_dialog import ReviewedActionDialog
    from ui.design.theme_manager import ThemeManager

    app = QApplication.instance() or QApplication([])
    original_font, original_style = app.font(), app.styleSheet()
    app.setFont(QFont("Sans Serif", point_size))
    ThemeManager().apply(app, theme)
    dialog = ReviewedActionDialog(
        "Change system setting: Parallel downloads",
        "Apply this exact setting value and verify it before reporting success.",
        "Setting: Parallel downloads\nCurrent: 3\nSelected: 10\nScope: this computer, all users.",
        "Automatic rollback is unavailable. After a verified change, Tweaks can offer the recorded previous value for a separate verified restore.",
        require_no_rollback_acceptance=True,
    )
    try:
        available = dialog.screen().availableGeometry()
        width, height = min(720, available.width()), min(500, available.height())
        dialog.resize(width, height)
        dialog.show()
        QTest.qWaitForWindowExposed(dialog, 3000)
        app.processEvents()
        assert dialog.width() <= width, f"Review exceeds logical work-area width: {dialog.width()} > {width}"
        assert dialog.height() <= height, f"Review exceeds logical work-area height: {dialog.height()} > {height}"
        for button in (dialog.cancel_button, dialog.accept_button):
            position = button.mapTo(dialog, QPoint(0, 0))
            assert dialog.rect().contains(position)
            assert dialog.rect().contains(position + QPoint(button.width() - 1, button.height() - 1))
        assert dialog.scope_view.accessibleName()
        assert dialog.no_rollback_checkbox.accessibleDescription()
        assert dialog.cancel_button.isDefault()
        assert not dialog.accept_button.isEnabled()
        dialog.scope_view.setFocus()
        QTest.keyClick(dialog.scope_view, Qt.Key.Key_Tab)
        assert dialog.focusWidget() is dialog.no_rollback_checkbox, "Tab is trapped in scope text"
        QTest.keyClick(dialog.no_rollback_checkbox, Qt.Key.Key_Space)
        assert dialog.accepts_no_rollback and dialog.accept_button.isEnabled()
        if screenshot is not None:
            screenshot.parent.mkdir(parents=True, exist_ok=True)
            assert dialog.grab().save(str(screenshot))
        QTest.keyClick(dialog.no_rollback_checkbox, Qt.Key.Key_Escape)
        assert dialog.result() == QDialog.DialogCode.Rejected
        return {
            "theme": theme, "font_points": point_size,
            "platform": app.platformName(), "device_pixel_ratio": dialog.devicePixelRatioF(),
            "logical_test_area": [width, height],
            "dialog_size": [dialog.width(), dialog.height()],
            "checks": ["bounded_geometry", "visible_primary_buttons", "accessible_scope_and_acceptance",
                       "cancel_default", "tab_leaves_scope", "space_accepts_explicitly", "escape_cancels"],
        }
    finally:
        dialog.close()
        app.setFont(original_font)
        app.setStyleSheet(original_style)
        app.processEvents()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("offscreen", "wayland", "xcb"), default="offscreen")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "test-results" / "accessibility")
    parser.add_argument("--case", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--theme", default="dark", help=argparse.SUPPRESS)
    parser.add_argument("--font-points", type=int, default=12, help=argparse.SUPPRESS)
    parser.add_argument("--scale", default="1", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.case:
        sys.path.insert(0, str(ROOT / "loofi-fedora-tweaks"))
        os.environ["QT_QPA_PLATFORM"] = args.platform
        os.environ["QT_SCALE_FACTOR"] = args.scale
        image = args.output_dir / f"review-{args.theme}-{args.scale}-{args.font_points}.png"
        print(json.dumps(check_case(args.theme, args.font_points, image), sort_keys=True))
        return 0
    args.output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for scale in ("1", "1.25", "1.5", "2"):
        for theme in ("light", "dark", "highcontrast"):
            for points in (12, 18):
                with tempfile.TemporaryDirectory(prefix="loofi-accessibility-") as directory:
                    env = os.environ.copy()
                    for kind in ("CONFIG", "DATA", "CACHE", "STATE"):
                        env[f"XDG_{kind}_HOME"] = str(Path(directory) / kind.lower())
                    result = subprocess.run(
                        [sys.executable, str(Path(__file__).resolve()), "--case", "--platform", args.platform,
                         "--output-dir", str(args.output_dir), "--theme", theme, "--font-points", str(points), "--scale", scale],
                        capture_output=True, text=True, check=True, timeout=30, env=env,
                    )
                results.append(json.loads(result.stdout))
    report = {"cases": results, "case_count": len(results), "scope": "Qt review-dialog geometry and keyboard automation"}
    (args.output_dir / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
