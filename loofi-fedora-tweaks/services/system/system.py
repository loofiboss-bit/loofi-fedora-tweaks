"""
System Manager - Central system detection and abstraction layer.
Handles detection of Fedora Atomic variants (Silverblue, Kinoite, etc.)
"""

import json
import os
import shutil
import subprocess
from functools import lru_cache
from typing import TYPE_CHECKING, cast

from utils.log import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from core.platform.profile import PlatformProfile


@lru_cache(maxsize=64)
def cached_which(tool: str) -> str | None:
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
    _is_atomic_cached: bool | None = None
    _pending_reboot_cached: bool | None = None

    @classmethod
    def get_platform_profile(cls) -> "PlatformProfile":
        """Return the immutable PlatformProfile for the host system."""
        from core.platform.profile import detect_platform_profile

        return detect_platform_profile(reboot_pending_checker=cls._check_reboot_pending)

    @classmethod
    def _check_reboot_pending(cls) -> bool | None:
        """Read deployment state without guessing when it is unavailable.

        rpm-ostree exposes enough deployment metadata to determine whether an
        unbooted deployment is staged.  bootc intentionally remains unknown:
        its deployment lifecycle is not represented by the rpm-ostree JSON
        schema and a false result would be unsafe.  Probe errors likewise
        return ``None`` instead of claiming that no reboot is required.
        """
        # bootc and rpm-ostree markers should not be conflated.  Prefer the
        # explicit bootc marker when both are visible during a transition.
        try:
            if os.path.exists("/run/bootc-booted"):
                return None
            if not os.path.exists("/run/ostree-booted"):
                return False
        except OSError as exc:
            logger.debug("Failed to inspect deployment marker: %s", exc)
            return None

        try:
            result = subprocess.run(
                ["rpm-ostree", "status", "--json"],
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
            )
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as exc:
            logger.debug("Failed to check pending deployment: %s", exc)
            return None

        if result.returncode != 0:
            logger.debug(
                "rpm-ostree status failed while checking reboot state: %s",
                result.returncode,
            )
            return None

        try:
            data = json.loads(result.stdout)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            logger.debug("Failed to check pending deployment: %s", exc)
            return None

        deployments = data.get("deployments") if isinstance(data, dict) else None
        if not isinstance(deployments, list):
            return None
        if not deployments:
            # Empty data is a malformed/incomplete probe, not proof of a
            # clean deployment.
            return None

        first = deployments[0]
        if not isinstance(first, dict):
            return None
        first_booted = first.get("booted")
        if first_booted is True:
            return False
        if first_booted is False and any(
            isinstance(deployment, dict) and deployment.get("booted") is True
            for deployment in deployments[1:]
        ):
            return True
        return None

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
    def is_immutable(cls) -> bool:
        """Return the immutable marker without authorizing a backend command."""
        return bool(cls.get_platform_profile().is_atomic)

    @classmethod
    def get_variant_name(cls) -> str:
        """
        Get the name of the Fedora variant. Fail-closed: never defaults to Workstation.

        Returns:
            String like "Silverblue", "Kinoite", "Workstation", etc., or "Unknown".
        """
        profile = cast("PlatformProfile", cls.get_platform_profile())
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
    def has_pending_deployment(cls) -> bool | None:
        """Return pending deployment state, preserving an unknown result.

        ``False`` is only returned for a known non-atomic backend or a
        successful rpm-ostree probe with no staged deployment.  bootc,
        unknown backends, and failed probes return ``None``.
        """
        from core.platform.profile import DeploymentBackend

        profile = cls.get_platform_profile()
        if profile.deployment_backend is DeploymentBackend.DNF5:
            if profile.reboot_pending is not None:
                return bool(profile.reboot_pending)
            return False
        if profile.deployment_backend is DeploymentBackend.BOOTC:
            return cast(bool | None, profile.reboot_pending)
        if profile.deployment_backend is DeploymentBackend.UNKNOWN:
            return None
        if profile.reboot_pending is not None:
            return bool(profile.reboot_pending)
        return cls._check_reboot_pending()

    @classmethod
    def get_layered_packages(cls) -> list[str]:
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
                        if not isinstance(dep, dict) or dep.get("booted") is not True:
                            continue
                        local_packages = dep.get("requested-local-packages", [])
                        requested_packages = dep.get("requested-packages", [])
                        if not isinstance(local_packages, list) or not isinstance(requested_packages, list):
                            return []
                        return [
                            package
                            for package in [*local_packages, *requested_packages]
                            if isinstance(package, str)
                        ]
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
