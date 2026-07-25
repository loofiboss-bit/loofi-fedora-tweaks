"""
Package service module — v23.0 Architecture Hardening.

Provides BasePackageService interface and concrete implementations
for DNF and rpm-ostree package management.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from services.package.base import BasePackageService
from services.package.dnf5_health import DNF5HealthReport, DNF5HealthService, RepoRisk

if TYPE_CHECKING:
    from services.package.service import (
        DnfPackageService,
        RpmOstreePackageService,
        get_package_service,
    )

_SERVICE_EXPORTS = {
    "DnfPackageService": ("services.package.service", "DnfPackageService"),
    "RpmOstreePackageService": ("services.package.service", "RpmOstreePackageService"),
    "get_package_service": ("services.package.service", "get_package_service"),
}


def __getattr__(name: str):
    """Lazily resolve service exports without importing PyQt6 on module import."""
    location = _SERVICE_EXPORTS.get(name)
    if location is None:
        raise AttributeError(name)
    from importlib import import_module

    module = import_module(location[0])
    return getattr(module, location[1])


__all__ = [
    "BasePackageService",
    "DnfPackageService",
    "DNF5HealthReport",
    "DNF5HealthService",
    "RpmOstreePackageService",
    "RepoRisk",
    "get_package_service",
]
