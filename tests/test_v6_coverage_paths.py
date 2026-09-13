"""Focused coverage for v6 command and dashboard paths."""

from __future__ import annotations

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))

from PyQt6.QtWidgets import QApplication

from core.diagnostics.release_readiness import ReadinessCheck, ReleaseReadinessReport, TARGETS
from ui.atlas_dashboard_tab import AtlasDashboardTab
from ui.fedora44_readiness_dialog import Fedora44ReadinessDialog
from ui.release_readiness_dialog import ReadinessWorker, ReleaseReadinessDialog


def test_atlas_dashboard_is_the_canonical_home_contract():
    assert AtlasDashboardTab._METADATA.id == "atlas_dashboard"
    assert AtlasDashboardTab._METADATA.name == "Home"


def test_fedora44_dialog_wrapper_instantiates():
    dialog = Fedora44ReadinessDialog(auto_run=False)
    assert dialog.target_key == "44"


def test_release_readiness_dialog_worker_and_actions():
    report = ReleaseReadinessReport(
        target="Fedora KDE 44",
        generated_at=1.0,
        score=100,
        status="ready",
        summary="ready",
        checks=[
            ReadinessCheck(
                id="fedora-version",
                title="Fedora Version",
                category="system",
                status="pass",
                severity="info",
                summary="Fedora 44",
                beginner_guidance="ok",
                command_preview=["cat", "/etc/os-release"],
                advanced_detail="detail",
            )
        ],
        target_metadata=TARGETS["44"],
    )

    dialog = ReleaseReadinessDialog(auto_run=False)
    dialog.report = report
    dialog.advanced_toggle.setChecked(True)
    dialog.copy_support_summary()
    assert "Fedora KDE 44" in QApplication.clipboard().text()

    dialog.severity_filter.setCurrentIndex(dialog.severity_filter.findData("error"))
    dialog._render()

    with patch("ui.release_readiness_dialog.ReleaseReadiness.run", return_value=report):
        worker = ReadinessWorker("44")
        seen = []
        worker.finished.connect(seen.append)
        worker.run()
        assert seen[0] is report

    with patch("ui.release_readiness_dialog.ReleaseReadiness.run", side_effect=RuntimeError("boom")):
        worker = ReadinessWorker("44")
        errors = []
        worker.failed.connect(errors.append)
        worker.run()
        assert errors == ["boom"]

    with patch("ui.release_readiness_dialog.QFileDialog.getSaveFileName", return_value=("/tmp/test.json", "")):
        with patch("ui.release_readiness_dialog.SupportBundleWriter.save_json", side_effect=OSError("no")):
            with patch("ui.release_readiness_dialog.QMessageBox.warning") as warning:
                dialog.export_support_bundle()
                warning.assert_called_once()
