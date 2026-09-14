"""Read-only system facts for the first-run welcome surface."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from core.fedora_release_policy import FEDORA_RELEASE_POLICY
from services.system.system import SystemManager


@dataclass(frozen=True)
class WelcomeSystemSummary:
    """Bounded, non-mutating facts shown before Home opens."""

    fedora_name: str
    fedora_version: str
    variant: str
    package_manager: str
    deployment_mode: str
    behavior: str
    support_status: str
    support_detail: str


def _read_os_release(path: Path = Path("/etc/os-release")) -> dict[str, str]:
    """Parse os-release without starting a process or probing the network."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}

    release: dict[str, str] = {}
    for line in text.splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        release[key.strip()] = value.strip().strip('"').strip("'")
    return release


def _support_for_version(version: str) -> tuple[str, str]:
    classification = FEDORA_RELEASE_POLICY.classify_host(version)
    if classification == "supported":
        return "Supported", f"Fedora {version} is a verified stable release for this product version."
    if classification == "preview":
        return "Preview", f"Fedora {FEDORA_RELEASE_POLICY.preview_release} support is advisory and remains read-only where capability policy requires it."
    if version:
        stable = ", ".join(FEDORA_RELEASE_POLICY.supported_stable_releases)
        return "Not verified", f"Fedora {version} is outside this release's verified Fedora {stable} targets."
    return "Unknown", "The Fedora release could not be identified; availability remains capability-aware."


def collect_welcome_system_summary(
    *,
    release: Mapping[str, str] | None = None,
    atomic: bool | None = None,
) -> WelcomeSystemSummary:
    """Collect local presentation facts without changing the system."""
    release_data = dict(release) if release is not None else _read_os_release()
    profile = None
    if atomic is None:
        profile = SystemManager.get_platform_profile()
        is_atomic = bool(profile.is_atomic)
    else:
        is_atomic = bool(atomic)
    version = str(release_data.get("VERSION_ID", "")).strip()
    variant = str(release_data.get("VARIANT", "")).strip()
    if not variant:
        variant = SystemManager.get_variant_name()
    if profile is not None:
        package_manager = profile.package_manager_name
        deployment_mode = profile.deployment_backend.value
    else:
        package_manager = "rpm-ostree" if is_atomic else "dnf"
        deployment_mode = "Atomic" if is_atomic else "Traditional"
    if profile is not None and profile.deployment_backend.value == "bootc":
        behavior = "This bootc host is detected, but update and recovery actions remain manual until the backend capability is qualified."
    elif profile is not None and profile.deployment_backend.value == "unknown":
        behavior = "The deployment backend is unknown; update and recovery actions remain unavailable until the host can be identified safely."
    elif is_atomic:
        behavior = "Base-system package changes are staged as deployments and normally require a reboot."
    else:
        behavior = "Package changes use the traditional DNF transaction model with explicit preview and confirmation."
    status, support_detail = _support_for_version(version)
    fedora_name = str(release_data.get("PRETTY_NAME", "")).strip()
    if not fedora_name:
        fedora_name = f"Fedora {version}" if version else "Fedora"
    return WelcomeSystemSummary(
        fedora_name=fedora_name,
        fedora_version=version or "Unknown",
        variant=variant or deployment_mode,
        package_manager=package_manager,
        deployment_mode=deployment_mode,
        behavior=behavior,
        support_status=status,
        support_detail=support_detail,
    )
