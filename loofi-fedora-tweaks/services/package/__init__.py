"""
Package service module — v23.0 Architecture Hardening.

Provides BasePackageService interface and concrete implementations
for DNF and rpm-ostree package management.
"""

from services.package.base import BasePackageService
from services.package.dnf5_health import DNF5HealthReport, DNF5HealthService, RepoRisk
from services.package.service import (
    DnfPackageService,
    RpmOstreePackageService,
    get_package_service,
)

__all__ = [
    "BasePackageService",
    "DnfPackageService",
    "DNF5HealthReport",
    "DNF5HealthService",
    "RpmOstreePackageService",
    "RepoRisk",
    "get_package_service",
]
