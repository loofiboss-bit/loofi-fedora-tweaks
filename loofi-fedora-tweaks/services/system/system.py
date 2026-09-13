"""
System Manager - Central system detection and abstraction layer.
Handles detection of Fedora Atomic variants (Silverblue, Kinoite, etc.)
"""

import os
import shutil
import subprocess
from functools import lru_cache
from typing import Any, Optional

from utils.log import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=64)
def cached_which(tool: str) -> Optional[str]:
    """Cached wrapper around shutil.which() to avoid repeated PATH lookups.

    Args:
        tool: Name of the executable to find.

    Returns:
        Full path to the executable, or None if not found.
    """
    return shutil.which(tool)


class SystemManager:
    """Manages system detection and provides system-level information."""

    # Cache the result to avoid repeated filesystem checks
    _is_atomic_cached = None
    _pending_reboot_cached = None

    @classmethod
    def get_platform_profile(cls) -> Any:
        """Return the immutable PlatformProfile for the host system."""
        from core.platform.profile import detect_platform_profile

        return detect_platform_profile(reboot_pending_checker=cls._check_reboot_pending)

    @classmethod
    def _check_reboot_pending(cls) -> bool:
        if not os.path.exists("/run/ostree-booted"):
            return False
        try:
            result = subprocess.run(
                ["rpm-ostree", "status", "--json"],
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
            )
            if result.returncode == 0:
                import json

                data = json.loads(result.stdout)
                deployments = data.get("deployments", [])
                if len(deployments) > 1:
                    return not deployments[0].get("booted", False)
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError, ValueError) as e:
            logger.debug("Failed to check pending deployment: %s", e)
        return False

    @classmethod
    def is_atomic(cls) -> bool:
        """
        Check if running on an Atomic/Immutable Fedora variant.
        (Silverblue, Kinoite, Sericea, Onyx, or any OSTree-based system)

        Returns:
            True if running on an Atomic system, False otherwise.
        """
        if cls._is_atomic_cached is None:
            profile = cls.get_platform_profile()
            cls._is_atomic_cached = bool(profile.is_atomic)
        return cls._is_atomic_cached

    @classmethod
    def get_variant_name(cls) -> str:
        """
        Get the name of the Fedora variant. Fail-closed: never defaults to Workstation.

        Returns:
            String like "Silverblue", "Kinoite", "Workstation", etc., or "Unknown".
        """
        profile = cls.get_platform_profile()
        if profile.variant_name:
            return str(profile.variant_name)
        if profile.variant_id and profile.variant_id not in ("unknown", "non-fedora"):
            return str(profile.variant_id).replace("_", " ").replace("-", " ").title()
        return "Unknown"

    @classmethod
    def get_package_manager(cls) -> str:
        """
        Get the appropriate package manager for this system.

        Returns:
            'rpm-ostree', 'dnf5', 'bootc', or 'unknown'.
        """
        profile = cls.get_platform_profile()
        return str(profile.package_manager_name)

    @classmethod
    def has_pending_deployment(cls) -> bool:
        """Check if there's a pending deployment waiting for reboot."""
        profile = cls.get_platform_profile()
        if not profile.is_atomic:
            return False
        if profile.reboot_pending is not None:
            return bool(profile.reboot_pending)
        return cls._check_reboot_pending()

    @classmethod
    def get_layered_packages(cls) -> list:
        """Get list of layered (overlayed) packages on Atomic systems.

        Behavior contract (v2.11.0 TASK-006):
        - Intentional local-read: rpm-ostree status --json parse.
        - No daemon expansion; package list is session-local query.
        - Returns empty list on non-atomic systems or parse errors (safe fallback).

        Returns:
            List of package names layered on top of the base image.
        """
        if not cls.is_atomic():
            return []

        try:
            result = subprocess.run(
                ["rpm-ostree", "status", "--json"],
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
            )
            if result.returncode == 0:
                import json

                data = json.loads(result.stdout)
                deployments = data.get("deployments", [])
                if deployments:
                    # Get the booted deployment
                    for dep in deployments:
                        if dep.get("booted", False):
                            pkgs: list[Any] = dep.get(
                                "requested-local-packages", []
                            ) + dep.get("requested-packages", [])
                            return pkgs
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError, json.JSONDecodeError) as e:
            logger.debug("Failed to get layered packages: %s", e)

        return []

    @classmethod
    def is_flatpak_available(cls) -> bool:
        """Check if Flatpak is installed and available."""
        return cached_which("flatpak") is not None

    @classmethod
    def is_flathub_enabled(cls) -> bool:
        """Check if Flathub remote is configured."""
        try:
            result = subprocess.run(
                ["flatpak", "remotes"], capture_output=True, text=True, check=False,
                timeout=10
            )
            return "flathub" in result.stdout.lower()
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e:
            logger.debug("Failed to check Flathub remote: %s", e)
            return False
