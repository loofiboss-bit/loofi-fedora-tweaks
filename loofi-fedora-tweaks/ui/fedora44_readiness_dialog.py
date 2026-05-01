"""Compatibility wrapper for the Fedora KDE 44 readiness dialog."""

from __future__ import annotations

from ui.release_readiness_dialog import ReleaseReadinessDialog


class Fedora44ReadinessDialog(ReleaseReadinessDialog):
    """Open the generic readiness dialog on the Fedora KDE 44 profile."""

    def __init__(self, parent=None, *, auto_run: bool = True):
        super().__init__("44", parent, auto_run=auto_run)
