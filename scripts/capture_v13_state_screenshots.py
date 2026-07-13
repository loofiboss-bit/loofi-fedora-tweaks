#!/usr/bin/env python3
"""Capture the real Settings State & Recovery page for v13 docs."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "loofi-fedora-tweaks"))

from PyQt6.QtWidgets import QApplication  # noqa: E402
from ui.settings_tab import SettingsTab  # noqa: E402


def main() -> int:
    app = QApplication.instance() or QApplication([])
    widget = SettingsTab()
    widget.resize(1100, 760)
    widget.settings_tabs.setCurrentIndex(3)
    widget._run_state_doctor()
    widget.show()
    app.processEvents()
    output = ROOT / "docs" / "images" / "user-guide" / "state-doctor.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    if not widget.grab().save(str(output)):
        raise RuntimeError(f"Unable to save {output}")
    print(output)
    with tempfile.TemporaryDirectory() as tmp:
        from core.state import StateArchiveService

        archive = Path(tmp) / "state.zip"
        StateArchiveService().backup(archive)
        widget._preview_state_restore(str(archive))
        app.processEvents()
        restore_output = output.with_name("restore-preview.png")
        if not widget.grab().save(str(restore_output)):
            raise RuntimeError(f"Unable to save {restore_output}")
        print(restore_output)
    widget._show_collector_status()
    app.processEvents()
    collector_output = output.with_name("collector-status.png")
    if not widget.grab().save(str(collector_output)):
        raise RuntimeError(f"Unable to save {collector_output}")
    print(collector_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
