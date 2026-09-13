"""Immutable, fail-closed Fedora platform detection and capability profiling.

This module provides the central PlatformProfile dataclass. Unknown detection
never defaults to Workstation, Traditional, or 'no reboot needed'.
"""

from __future__ import annotations

import os
import platform
import shutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Mapping


class DeploymentBackend(str, Enum):
    """Underlying package and OS deployment technology."""

    DNF5 = "dnf5"
    RPM_OSTREE = "rpm_ostree"
    BOOTC = "bootc"
    UNKNOWN = "unknown"

    @property
    def is_atomic(self) -> bool:
        return self in (DeploymentBackend.RPM_OSTREE, DeploymentBackend.BOOTC)


class DesktopEnvironment(str, Enum):
    """Detected desktop environment."""

    GNOME = "gnome"
    KDE = "kde"
    XFCE = "xfce"
    SWAY = "sway"
    COSMIC = "cosmic"
    CINNAMON = "cinnamon"
    MATE = "mate"
    LXQT = "lxqt"
    UNKNOWN = "unknown"


class SessionType(str, Enum):
    """Display session protocol."""

    WAYLAND = "wayland"
    X11 = "x11"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PlatformProfile:
    """Immutable, typed snapshot of the host platform and deployment stack."""

    os_id: str
    fedora_version: int | None
    variant_id: str
    variant_name: str
    architecture: str
    desktop: DesktopEnvironment
    session_type: SessionType
    deployment_backend: DeploymentBackend
    is_atomic: bool
    reboot_pending: bool | None = None

    @property
    def is_fedora(self) -> bool:
        return self.os_id == "fedora" and self.fedora_version is not None

    @property
    def is_supported_release(self) -> bool:
        """Supported stable releases for v27 are Fedora 43 and 44."""
        return self.is_fedora and self.fedora_version in (43, 44)

    @property
    def is_preview_release(self) -> bool:
        return self.is_fedora and self.fedora_version == 45

    @property
    def package_manager_name(self) -> str:
        """Command name for package management handoffs."""
        if self.deployment_backend is DeploymentBackend.RPM_OSTREE:
            return "rpm-ostree"
        if self.deployment_backend is DeploymentBackend.BOOTC:
            return "bootc"
        if self.deployment_backend is DeploymentBackend.DNF5:
            return "dnf5"
        return "unknown"


def _parse_os_release(path: Path) -> dict[str, str]:
    """Parse key-value pairs from an os-release file safely."""
    data: dict[str, str] = {}
    if not path.is_file():
        return data
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return data

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            data[key] = val
    return data


def detect_desktop(env: Mapping[str, str] | None = None) -> DesktopEnvironment:
    """Detect desktop environment from environment variables."""
    if env is None:
        env = os.environ

    xdg_desktop = (env.get("XDG_CURRENT_DESKTOP") or "").upper()
    desktop_session = (env.get("DESKTOP_SESSION") or "").upper()

    combined = f"{xdg_desktop}:{desktop_session}"

    if "KDE" in combined or "PLASMA" in combined:
        return DesktopEnvironment.KDE
    if "GNOME" in combined:
        return DesktopEnvironment.GNOME
    if "XFCE" in combined:
        return DesktopEnvironment.XFCE
    if "SWAY" in combined:
        return DesktopEnvironment.SWAY
    if "COSMIC" in combined:
        return DesktopEnvironment.COSMIC
    if "CINNAMON" in combined:
        return DesktopEnvironment.CINNAMON
    if "MATE" in combined:
        return DesktopEnvironment.MATE
    if "LXQT" in combined:
        return DesktopEnvironment.LXQT

    return DesktopEnvironment.UNKNOWN


def detect_session_type(env: Mapping[str, str] | None = None) -> SessionType:
    """Detect session type from environment variables."""
    if env is None:
        env = os.environ

    val = (env.get("XDG_SESSION_TYPE") or "").lower()
    if val == "wayland":
        return SessionType.WAYLAND
    if val == "x11":
        return SessionType.X11
    if env.get("WAYLAND_DISPLAY"):
        return SessionType.WAYLAND
    if env.get("DISPLAY"):
        return SessionType.X11
    return SessionType.UNKNOWN


def detect_deployment_backend(
    *,
    is_atomic: bool,
    is_bootc: bool = False,
    which_cmd: Callable[[str], str | None] = shutil.which,
) -> DeploymentBackend:
    """Detect the deployment backend without assuming Workstation or Traditional."""
    if is_bootc:
        return DeploymentBackend.BOOTC
    if is_atomic:
        return DeploymentBackend.RPM_OSTREE

    # For non-atomic systems: check dnf5 availability
    if which_cmd("dnf5") is not None:
        return DeploymentBackend.DNF5
    if which_cmd("dnf") is not None:
        return DeploymentBackend.DNF5

    return DeploymentBackend.UNKNOWN


def detect_platform_profile(
    *,
    os_release_path: Path = Path("/etc/os-release"),
    ostree_booted_path: Path = Path("/run/ostree-booted"),
    bootc_booted_path: Path = Path("/run/bootc-booted"),
    env: Mapping[str, str] | None = None,
    which_cmd: Callable[[str], str | None] = shutil.which,
    reboot_pending_checker: Callable[[], bool] | None = None,
) -> PlatformProfile:
    """Detect and construct the immutable PlatformProfile for the current host.

    Fail-closed behavior:
    - Non-Fedora distributions have fedora_version=None.
    - Missing ostree-booted is NOT automatically Workstation or Traditional.
    - Unknown backends and desktops are preserved as UNKNOWN.
    """
    os_data = _parse_os_release(os_release_path)
    os_id = os_data.get("ID", "").lower()

    fedora_ver: int | None = None
    if os_id == "fedora":
        raw_version = os_data.get("VERSION_ID", "")
        if raw_version.isdigit():
            fedora_ver = int(raw_version)

    variant_id = os_data.get("VARIANT_ID", "").lower()
    variant_name = os_data.get("VARIANT", "") or os_data.get("NAME", "Unknown")

    is_bootc = bootc_booted_path.exists()
    is_atomic = ostree_booted_path.exists() or is_bootc

    # If variant is empty, do NOT fall back to Workstation
    if not variant_id:
        if is_atomic:
            variant_id = "atomic"
        elif fedora_ver is not None:
            variant_id = "unknown"
        else:
            variant_id = "non-fedora"

    architecture = platform.machine() or "unknown"
    desktop = detect_desktop(env)
    session_type = detect_session_type(env)
    deployment_backend = detect_deployment_backend(
        is_atomic=is_atomic,
        is_bootc=is_bootc,
        which_cmd=which_cmd,
    )

    reboot_pending: bool | None = None
    if reboot_pending_checker is not None:
        try:
            reboot_pending = reboot_pending_checker()
        except (OSError, RuntimeError, ValueError, TypeError, AttributeError):
            reboot_pending = None

    return PlatformProfile(
        os_id=os_id,
        fedora_version=fedora_ver,
        variant_id=variant_id,
        variant_name=variant_name,
        architecture=architecture,
        desktop=desktop,
        session_type=session_type,
        deployment_backend=deployment_backend,
        is_atomic=is_atomic,
        reboot_pending=reboot_pending,
    )
