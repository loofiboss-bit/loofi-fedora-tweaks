#!/usr/bin/env python3
"""Render scoped update fixtures offscreen without observing the host."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "loofi-fedora-tweaks"))


def capture(output: Path, scale: str, large_text: bool) -> None:
    os.environ.update(QT_QPA_PLATFORM="offscreen", QT_SCALE_FACTOR=scale, LOOFI_IPC_MODE="disabled")
    with tempfile.TemporaryDirectory(prefix="loofi-flatpak-render-") as directory:
        for kind in ("CONFIG", "DATA", "CACHE", "STATE"):
            os.environ[f"XDG_{kind}_HOME"] = str(Path(directory) / kind.lower())
        from PyQt6.QtCore import Qt
        from PyQt6.QtTest import QTest
        from PyQt6.QtWidgets import QApplication, QLabel, QScrollArea
        from ui.confirm_dialog import ReviewedActionDialog
        from ui.design import ThemeManager
        from ui.flatpak_updates import FlatpakUpdatesCard, flatpak_review_lines

        app = QApplication.instance() or QApplication([])
        if large_text:
            font = app.font()
            font.setPointSizeF(max(10, font.pointSizeF()) * 1.4)
            app.setFont(font)
        output.mkdir(parents=True, exist_ok=True)
        records = []
        base = dict(ref="app/org.example.Editor/x86_64/stable", origin="local-reviewed-source", name="Example editor with a longer application name",
                    installed_commit="a" * 64, expected_commit="b" * 64, installed_version="2026.10.1", available_version="2026.10.2")
        candidates = [{**base, "installation": scope} for scope in ("user", "system", "work-apps")]
        operations = [{**candidates[0], "selected": True, "operation": "update"},
                      {**candidates[0], "ref": "runtime/org.example.Platform/x86_64/stable", "name": "Required runtime",
                       "selected": False, "operation": "install"}]
        plan = SimpleNamespace(policy_decision=SimpleNamespace(facts={"flatpak_updates": {
            "installations": [{"installation": "user", "operations": operations}]}}))
        with patch("subprocess.run", side_effect=AssertionError("Host probes prohibited")), \
                patch("subprocess.Popen", side_effect=AssertionError("Host processes prohibited")):
            for theme in ("light", "dark", "high_contrast"):
                ThemeManager().apply(app, theme)
                for width, height in ((900, 650), (1280, 800), (1600, 900)):
                    for state in ("candidates", "partial", "result", "review"):
                        card = None
                        if state == "review":
                            summary, details = flatpak_review_lines(plan, str)
                            widget = ReviewedActionDialog("Update selected Flatpak applications", "Review the apps and required dependencies.",
                                                          "\n".join(summary), "No automatic rollback. Application data is preserved.")
                            widget.add_technical_details("\n".join(details))
                        else:
                            card = FlatpakUpdatesCard(service=Mock())
                            snapshot = dict(available=True, status="available", checked_at="2026-10-16T12:00:00Z", candidates=candidates)
                            if state == "partial":
                                snapshot.update(status="partial", candidates=candidates[:1], installations=[{
                                    "installation": "work-apps", "error": "The installation could not be checked. Retry explicitly."}])
                            card.apply_snapshot(snapshot)
                            if state == "result":
                                card.set_outcome(SimpleNamespace(run_id="fixture-run", message="Some results need attention.", plan=plan,
                                    data={"verification_result": {"data": {"results": [
                                        {"installation": "user", "ref": base["ref"], "status": "verified"},
                                        {"installation": "user", "ref": operations[1]["ref"], "status": "unverified"}]}}}), "user")
                            widget = QScrollArea()
                            widget.setWidgetResizable(True)
                            widget.setWidget(card)
                        widget.resize(width, height)
                        widget.show()
                        app.processEvents()
                        if card is not None:
                            card.check_button.setFocus()
                            QTest.keyClick(card.check_button, Qt.Key.Key_Tab)
                        else:
                            widget.cancel_button.setFocus()
                            assert widget.cancel_button.isDefault()
                        app.processEvents()
                        clipping = []
                        for label in widget.findChildren(QLabel):
                            if label.isVisible() and label.wordWrap() and label.heightForWidth(label.width()) > label.height() + 2:
                                clipping.append(label.text())
                        horizontal = widget.horizontalScrollBar().maximum() if isinstance(widget, QScrollArea) else widget.review_scroll.horizontalScrollBar().maximum()
                        name = f"{state}-{theme}-{width}x{height}-scale{scale}-large{int(large_text)}.png"
                        assert widget.grab().save(str(output / name))
                        records.append({"capture": name, "wrapped_label_clipping": clipping, "horizontal_overflow": horizontal,
                                        "focus_present": app.focusWidget() is not None})
                        widget.close()
                        widget.deleteLater()
                        app.processEvents()
        (output / "rendering-checks.json").write_text(json.dumps(records, indent=2) + "\n")
        failures = [row for row in records if row["wrapped_label_clipping"] or row["horizontal_overflow"] or not row["focus_present"]]
        print(json.dumps({"captures": len(records), "failures": len(failures), "scale": scale, "large_text": large_text}))
        if failures:
            raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--scale", choices=("1", "1.5", "2"), default="1")
    parser.add_argument("--large-text", action="store_true")
    args = parser.parse_args()
    capture(args.output, args.scale, args.large_text)
