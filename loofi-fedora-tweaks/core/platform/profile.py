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
from typing import Callable, Mapping

from core.fedora_release_policy import FEDORA_RELEASE_POLICY, FedoraSupportStatus


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


class RebootStatus(str, Enum):
    """Authoritative state of a reboot check.

    ``UNKNOWN`` is deliberately first-class.  A failed or unsupported probe
    must never be rendered as ``NOT_REQUIRED`` because doing so can make a
    staged deployment look safe to continue using.
    """

    REQUIRED = "required"
    NOT_REQUIRED = "not_required"
    UNKNOWN = "unknown"


# ``RebootState`` is a readable compatibility alias for callers that model
# the value as a state rather than a status.  Both names refer to one enum.
RebootState = RebootStatus


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
    # The backend is semantic (DNF5) while the executable can still be the
    # legacy ``dnf`` name on older Fedora images.  Keep that observation so a
    # caller does not render an unavailable command when only ``dnf`` exists.
    package_manager_command: str | None = None

    @property
    def is_fedora(self) -> bool:
        return self.os_id == "fedora" and self.fedora_version is not None

    @property
    def is_supported_release(self) -> bool:
        """Return whether the host is one of the verified stable releases."""
        return self.is_fedora and FEDORA_RELEASE_POLICY.is_supported_version(
            str(self.fedora_version)
        )

    @property
    def is_preview_release(self) -> bool:
        return self.is_fedora and FEDORA_RELEASE_POLICY.is_preview_version(
            str(self.fedora_version)
        )

    @property
    def support_status(self) -> FedoraSupportStatus:
        """Return the central release-support classification."""
        if not self.is_fedora:
            return "unknown"
        return FEDORA_RELEASE_POLICY.classify_host(str(self.fedora_version))

    @property
    def package_manager_name(self) -> str:
        """Command name for package management handoffs."""
        if self.deployment_backend is DeploymentBackend.RPM_OSTREE:
            return "rpm-ostree"
        if self.deployment_backend is DeploymentBackend.BOOTC:
            return "bootc"
        if self.deployment_backend is DeploymentBackend.DNF5:
            return self.package_manager_command or "dnf5"
        return "unknown"

    @property
    def reboot_status(self) -> RebootStatus:
        """Return the reboot result without collapsing unknown into false."""
        if self.reboot_pending is True:
            return RebootStatus.REQUIRED
        if self.reboot_pending is False:
            return RebootStatus.NOT_REQUIRED
        return RebootStatus.UNKNOWN

    @property
    def reboot_state(self) -> RebootStatus:
        """Alias for :attr:`reboot_status` used by state-oriented callers."""
        return self.reboot_status

    def to_dict(self) -> dict[str, object]:
        """Serialize the profile using stable primitive values.

        Enum members are intentionally serialized through ``.value`` rather
        than ``str(member)``.  The latter produces strings such as
        ``"DeploymentBackend.DNF5"`` on Python versions supported by v27.
        """
        return {
            "os_id": self.os_id,
            "fedora_version": self.fedora_version,
            "support_status": self.support_status,
            "variant_id": self.variant_id,
            "variant_name": self.variant_name,
            "architecture": self.architecture,
            "desktop": self.desktop.value,
            "session_type": self.session_type.value,
            "deployment_backend": self.deployment_backend.value,
            "is_atomic": self.is_atomic,
            "reboot_pending": self.reboot_pending,
            "package_manager_command": self.package_manager_command,
            "reboot_status": self.reboot_status.value,
        }

    @classmethod
    def detect(cls, **kwargs: object) -> "PlatformProfile":
        """Build a profile through the canonical detector.

        Keeping detection behind this class method prevents callers from
        inventing a second, less strict fallback path.  The implementation is
        defined below the class so the existing keyword-only detector remains
        easy to unit-test with temporary paths.
        """
        return detect_platform_profile(**kwargs)  # type: ignore[arg-type]


def _parse_os_release(path: Path) -> dict[str, str]:
    """Parse key-value pairs from an os-release file safely."""
    data: dict[str, str] = {}
    try:
        if not path.is_file():
            return data
    except OSError:
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

    val = (env.get("XDG_SESSION_TYPE") or "").strip().lower()
    if val == "wayland":
        return SessionType.WAYLAND
    if val == "x11":
        return SessionType.X11
    # An explicitly supplied but unsupported session value must stay unknown;
    # guessing from DISPLAY in that case is not fail-closed.
    if val:
        return SessionType.UNKNOWN
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
    try:
        if which_cmd("dnf5") is not None:
            return DeploymentBackend.DNF5
        if which_cmd("dnf") is not None:
            return DeploymentBackend.DNF5
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        # A broken PATH probe is an unknown capability, never a traditional
        # fallback.
        return DeploymentBackend.UNKNOWN

    return DeploymentBackend.UNKNOWN


def detect_platform_profile(
    *,
    os_release_path: Path = Path("/etc/os-release"),
    ostree_booted_path: Path = Path("/run/ostree-booted"),
    bootc_booted_path: Path = Path("/run/bootc-booted"),
    env: Mapping[str, str] | None = None,
    which_cmd: Callable[[str], str | None] = shutil.which,
    reboot_pending_checker: Callable[[], bool | None] | None = None,
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
        raw_version = os_data.get("VERSION_ID", "").strip()
        # Atomic image VERSION_ID values may carry a build suffix (for
        # example ``44.20240901``); the leading Fedora major is still the
        # release identity.  Non-numeric values such as Rawhide stay unknown.
        major_version = raw_version.split(".", 1)[0]
        if major_version.isdigit():
            fedora_ver = int(major_version)

    variant_id = os_data.get("VARIANT_ID", "").lower()
    variant_name = os_data.get("VARIANT", "") or os_data.get("NAME", "") or "Unknown"

    marker_probe_ok = True
    try:
        is_bootc = bootc_booted_path.exists()
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        is_bootc = False
        marker_probe_ok = False
    try:
        is_ostree = ostree_booted_path.exists()
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        is_ostree = False
        marker_probe_ok = False
    is_atomic = is_ostree or is_bootc

    # If variant is empty, do NOT fall back to Workstation
    if not variant_id:
        if is_atomic:
            variant_id = "atomic"
        elif fedora_ver is not None:
            variant_id = "unknown"
        else:
            variant_id = "non-fedora"

    try:
        architecture = platform.machine() or "unknown"
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        architecture = "unknown"
    desktop = detect_desktop(env)
    session_type = detect_session_type(env)
    # Platform support is Fedora-scoped.  We still expose an observed
    # immutable/bootc marker on a foreign OS, but never infer a Fedora package
    # backend there from a coincidentally available executable.
    package_manager_command: str | None = None
    if os_id == "fedora" and marker_probe_ok:
        deployment_backend = detect_deployment_backend(
            is_atomic=is_atomic,
            is_bootc=is_bootc,
            which_cmd=which_cmd,
        )
        if deployment_backend is DeploymentBackend.DNF5:
            try:
                if which_cmd("dnf5") is not None:
                    package_manager_command = "dnf5"
                elif which_cmd("dnf") is not None:
                    package_manager_command = "dnf"
            except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
                package_manager_command = None
    else:
        deployment_backend = DeploymentBackend.UNKNOWN

    reboot_pending: bool | None = None
    # Do not invoke an arbitrary reboot checker for an unknown or foreign
    # platform.  This keeps the unknown result distinct from a real negative
    # probe and prevents a generic callback from authorizing unsafe actions.
    if (
        reboot_pending_checker is not None
        and os_id == "fedora"
        and deployment_backend in (DeploymentBackend.DNF5, DeploymentBackend.RPM_OSTREE)
    ):
        try:
            reboot_pending = reboot_pending_checker()
            if reboot_pending not in (True, False, None):
                reboot_pending = None
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
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
        package_manager_command=package_manager_command,
    )
