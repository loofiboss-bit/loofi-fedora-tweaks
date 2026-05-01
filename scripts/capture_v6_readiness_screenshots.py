#!/usr/bin/env python3
"""Capture v6 user-guide screenshots for the Release Readiness flow."""

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
from PyQt6.QtWidgets import QApplication, QScrollArea  # noqa: E402

from core.diagnostics.release_readiness import (  # noqa: E402
    ReadinessCheck,
    ReadinessRecommendation,
    ReleaseReadinessReport,
    TARGETS,
)
from ui.atlas_dashboard_tab import AtlasDashboardTab  # noqa: E402
from ui.release_readiness_dialog import ReleaseReadinessDialog  # noqa: E402


def _sample_report() -> ReleaseReadinessReport:
    repo_recommendation = ReadinessRecommendation(
        title="Review third-party repositories",
        description="Audit COPR and vendor repositories before major release work.",
        command_preview=["dnf5", "repolist", "--enabled"],
        risk_level="low",
        rollback_hint="Re-enable any manually disabled repo after upgrade validation.",
        docs_link="https://docs.fedoraproject.org/en-US/quick-docs/upgrading-fedora-offline/",
    )
    return ReleaseReadinessReport(
        target="Fedora KDE 44",
        generated_at=time.time(),
        score=91,
        status="ready",
        summary="Fedora KDE 44 readiness score 91/100 with 1 warning(s) and 0 error(s).",
        target_metadata=TARGETS["44"],
        checks=[
            ReadinessCheck(
                id="fedora-version",
                title="Fedora Version",
                category="system",
                status="pass",
                severity="info",
                summary="Fedora Linux 44 matches the supported Fedora KDE 44 target.",
                beginner_guidance="You are on the release this readiness profile checks.",
                command_preview=["cat", "/etc/os-release"],
            ),
            ReadinessCheck(
                id="kde-plasma-version",
                title="KDE Plasma Version",
                category="desktop",
                status="pass",
                severity="info",
                summary="Plasma version: 6.6.4",
                beginner_guidance="Plasma version looks compatible.",
                command_preview=["plasmashell", "--version"],
            ),
            ReadinessCheck(
                id="session-type",
                title="Wayland Session",
                category="desktop",
                status="pass",
                severity="info",
                summary="Session type: wayland",
                beginner_guidance="Wayland session detected.",
                command_preview=["printenv", "XDG_SESSION_TYPE"],
            ),
            ReadinessCheck(
                id="third-party-repos",
                title="Third-Party Repository Risk",
                category="package",
                status="warning",
                severity="warning",
                summary="5 third-party repository signal(s) found.",
                beginner_guidance="Review COPR and vendor repositories before major upgrades.",
                command_preview=["dnf5", "repolist", "--enabled"],
                advanced_detail="COPR and vendor repositories are useful, but they should be checked before release upgrades.",
                recommendation=repo_recommendation,
            ),
            ReadinessCheck(
                id="dnf-locks",
                title="DNF/RPM Locks",
                category="package",
                status="pass",
                severity="info",
                summary="No active DNF/RPM lock detected.",
                beginner_guidance="Package manager is not locked.",
                command_preview=["fuser", "/var/lib/dnf/metadata_lock.pid", "/var/lib/rpm/.rpm.lock"],
            ),
            ReadinessCheck(
                id="tls-cert-compat",
                title="TLS Certificate Compatibility",
                category="network",
                status="info",
                severity="info",
                summary="Fedora CA trust bundle exists at /etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem.",
                beginner_guidance="Fedora certificate trust is present; only legacy tools may expect /etc/pki/tls/cert.pem.",
                command_preview=["test", "-f", "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem"],
            ),
        ],
    )


def _settle() -> None:
    for _ in range(6):
        QApplication.processEvents()


def _capture(widget, filename: str, size: QSize) -> None:
    widget.resize(size)
    widget.show()
    _settle()
    pixmap = widget.grab()
    path = OUT / filename
    if not pixmap.save(str(path), "PNG"):
        raise RuntimeError(f"failed to save {path}")


def _prepare_dialog(
    *,
    advanced: bool = False,
    filter_key: str = "all",
    scroll: int = 0,
    minimum_size: QSize = QSize(1100, 820),
) -> ReleaseReadinessDialog:
    dialog = ReleaseReadinessDialog(auto_run=False)
    dialog.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
    dialog.setMinimumSize(minimum_size)
    filter_index = dialog.severity_filter.findData(filter_key)
    if filter_index >= 0:
        dialog.severity_filter.setCurrentIndex(filter_index)
    dialog.advanced_toggle.setChecked(advanced)
    dialog.report = _sample_report()
    dialog._render()
    _settle()
    scroll_area = dialog.findChild(QScrollArea)
    if scroll_area is not None:
        scroll_area.verticalScrollBar().setValue(scroll)
    return dialog


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    qss_path = SRC / "assets" / "modern.qss"
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))

    dashboard = AtlasDashboardTab()
    dashboard.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
    _capture(dashboard, "home-dashboard.png", QSize(1440, 760))

    dialog = _prepare_dialog(advanced=False, filter_key="all")
    _capture(dialog, "release-readiness.png", QSize(1100, 820))

    advanced = _prepare_dialog(advanced=True, filter_key="attention", minimum_size=QSize(1100, 620))
    _capture(advanced, "release-readiness-advanced.png", QSize(1100, 620))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
