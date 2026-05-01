"""Compatibility aliases for the Fedora KDE 44 readiness command."""

from __future__ import annotations

from core.diagnostics.release_readiness import (
    DNF5HealthService,
    Fedora44ReadinessReport,
    KDE44DesktopService,
    ReadinessCheck,
    ReadinessRecommendation,
    ReleaseReadiness,
    ReleaseReadinessReport,
    ReleaseTarget,
    TARGETS,
)


class Fedora44Readiness(ReleaseReadiness):
    """Backward-compatible Fedora KDE 44 readiness facade."""

    TARGET_KEY = "44"
    TARGET = "Fedora KDE 44"
    FEDORA_COMPAT_VERSION = "43"
    FEDORA_TARGET_VERSION = "44"


__all__ = [
    "DNF5HealthService",
    "Fedora44Readiness",
    "Fedora44ReadinessReport",
    "KDE44DesktopService",
    "ReadinessCheck",
    "ReadinessRecommendation",
    "ReleaseReadiness",
    "ReleaseReadinessReport",
    "ReleaseTarget",
    "TARGETS",
]
