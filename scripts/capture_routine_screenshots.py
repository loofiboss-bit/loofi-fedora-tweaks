#!/usr/bin/env python3
"""Render isolated Routine fixtures; no system observations or changes."""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "loofi-fedora-tweaks"))


def capture(output: Path, scale: str) -> None:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["QT_SCALE_FACTOR"] = scale
    os.environ["LOOFI_IPC_MODE"] = "disabled"
    with tempfile.TemporaryDirectory(prefix="loofi-routine-render-") as directory:
        for name in ("CONFIG", "DATA", "CACHE", "STATE"):
            os.environ[f"XDG_{name}_HOME"] = str(Path(directory) / name.lower())
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QApplication, QLabel, QDialog, QMainWindow, QScrollArea, QWidget
        from ui.design import ThemeManager
        from services.software.installed_applications import InstalledApplication, InstalledInventory
        from services.software.app_comparison import compare_installations
        from services.software.restart_advice import RestartAdvice
        from services.storage.space_guide import FilesystemObservation, SpaceGuide
        from core.tasks.tweak_library import LibraryEntry
        from core.tasks.tweak_profiles import TweakProfile
        from core.tasks.next_steps import NextStep, NextStepContext
        from core.troubleshooting.models import SourceResult
        from core.troubleshooting.lifecycle import new_session, start_session, finalize_session
        from ui.app_comparison import ApplicationComparisonDialog
        from ui.tweak_profile_comparison import ProfileComparisonDialog
        from ui.update_workflow import UpdateWorkflowPage
        from ui.overview_page import OverviewPage
        from ui.guide_panel import GuidePanel
        from ui.troubleshoot_widget import TroubleshootWidget
        stamp = time.time()
        apps = InstalledInventory((
            InstalledApplication("Firefox", "org.mozilla.firefox", "flatpak", "user", "app/org.mozilla.firefox/x86_64/stable", "142.0", "250 MB"),
            InstalledApplication("Firefox", "org.mozilla.firefox", "flatpak", "system", "app/org.mozilla.firefox/x86_64/beta", "143.0", "260 MB"),
            InstalledApplication("Firefox", "firefox", "fedora", "system", "firefox", "142.0-1.fc44", "180 MB"),
        ), ("An optional inventory source is unavailable.",), frozenset({"named-installation"}))
        profiles = (
            LibraryEntry("a" * 64, TweakProfile("Work", "kde", (("kde-focus-policy", "ClickToFocus"), ("kde-animation", "1")))),
            LibraryEntry("b" * 64, TweakProfile("Evening", "kde", (("kde-focus-policy", "FocusFollowsMouse"), ("kde-night-color", "true"), ("future-setting", "custom")))),
        )
        guide = SpaceGuide(stamp, False, (
            FilesystemObservation(("/", "/var"), "observed", 500_000_000_000, 480_000_000_000, 20_000_000_000, 96),
            FilesystemObservation(("/home",), "observed", 1_000_000_000_000, 250_000_000_000, 750_000_000_000, 25),
        ), None, 4_000_000_000)
        evidence = SourceResult.partial("storage-reclaim", started_at=stamp - 1, completed_at=stamp,
                                        timeout_seconds=25, facts={"space_guide": guide.to_dict()},
                                        reason_code="storage-observations-incomplete", message="The cache measurement is unavailable.")
        session = finalize_session(start_session(new_session("storage_pressure", "traditional", started_at=stamp - 1), started_at=stamp - 1),
                                   completed_at=stamp, source_results=(evidence,))
        app = QApplication.instance() or QApplication([])
        output.mkdir(parents=True, exist_ok=True)
        results = []
        with patch("subprocess.run", side_effect=AssertionError("Host reads prohibited in fixtures")), \
                patch("subprocess.Popen", side_effect=AssertionError("Host processes prohibited in fixtures")):
            for theme in ("light", "dark"):
                ThemeManager().apply(app, theme)
                for width, height in ((900, 650), (1280, 800)):
                    app_dialog = ApplicationComparisonDialog(compare_installations(apps, "org.mozilla.firefox"))
                    profile_dialog = ProfileComparisonDialog(profiles, profiles[0])
                    updates = UpdateWorkflowPage(service=Mock())
                    updates.restart_advice.service._advice = RestartAdvice("required", "2026-10-10T12:00:00+00:00", ("kernel", "systemd"), "dnf5_local_hint", False)
                    updates.restart_advice.refresh_display()
                    updates.preselect_source("system", "12345678-1234-5678-9234-567812345678")
                    overview = OverviewPage()
                    guides = GuidePanel()
                    guides.open_guide("maintain-your-system")
                    overview._show_next_steps((NextStep("failed", "Review unsuccessful changes", "Flatpak update needs review", "health", "Review changes",
                                                        stamp, NextStepContext(run_id="exact-run", update_source="flatpak")),))
                    history = Mock()
                    history.latest.return_value = (None, "")
                    history.sessions.return_value = ()
                    health = TroubleshootWidget(history=history)
                    health._current_session = session
                    health._select_symptom_card("storage_full")
                    health._render_session(session, None, "")
                    health._select_view("results")
                    for name, widget in (("app-comparison", app_dialog), ("profile-comparison", profile_dialog),
                                         ("updates", updates), ("overview-context", overview), ("health-storage", health),
                                         ("guide-flow", guides)):
                        if isinstance(widget, QDialog):
                            surface = widget
                        else:
                            surface = QMainWindow()
                            scroll = QScrollArea()
                            scroll.setWidgetResizable(True)
                            scroll.setWidget(widget)
                            surface.setCentralWidget(scroll)
                        surface.resize(width, height)
                        surface.show()
                        for _ in range(8):
                            app.processEvents()
                        path = output / f"{name}-{theme}-{width}x{height}-scale{scale}.png"
                        if surface.size().width() != width or surface.size().height() != height:
                            raise RuntimeError(f"Fixture exceeded requested viewport: {name}")
                        if not surface.grab().save(str(path)):
                            raise RuntimeError(f"Could not save {path}")
                        clipping = [label.objectName() or label.text()[:50] for label in widget.findChildren(QLabel)
                                    if label.isVisibleTo(widget) and label.wordWrap() and label.heightForWidth(label.width()) > label.height() + 1]
                        focus = [child.objectName() or type(child).__name__ for child in widget.findChildren(QWidget)
                                 if child.isVisibleTo(widget) and child.isEnabled() and child.focusPolicy() & Qt.FocusPolicy.TabFocus]
                        results.append({"view": name, "theme": theme, "size": [width, height], "scale": scale,
                                        "path": str(path), "wrapped_label_clipping": clipping, "tab_focus_targets": focus})
                        cleanup = getattr(widget, "cleanup", None)
                        if callable(cleanup):
                            cleanup()
                        surface.close()
                        surface.deleteLater()
                        app.processEvents()
        (output / f"rendering-scale{scale}.json").write_text(json.dumps(results, indent=2) + "\n")
        print(json.dumps({"captures": len(results), "scale": scale, "wrapped_label_clipping_views": sum(bool(row["wrapped_label_clipping"]) for row in results)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--scale", default="1", choices=("1", "2"))
    args = parser.parse_args()
    capture(args.output, args.scale)
