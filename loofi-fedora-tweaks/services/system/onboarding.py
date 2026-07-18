"""Read-only system facts for the first-run welcome surface."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

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
    if version == "44":
        return "Supported", "Fedora 44 is the verified stable target for this release."
    if version == "45":
        return "Preview", "Fedora 45 support is advisory and remains read-only where capability policy requires it."
    if version:
        return "Not verified", f"Fedora {version} is outside this release's verified Fedora 44 target."
    return "Unknown", "The Fedora release could not be identified; availability remains capability-aware."


def collect_welcome_system_summary(
    *,
    release: Mapping[str, str] | None = None,
    atomic: bool | None = None,
) -> WelcomeSystemSummary:
    """Collect local presentation facts without changing the system."""
    release_data = dict(release) if release is not None else _read_os_release()
    is_atomic = SystemManager.is_atomic() if atomic is None else bool(atomic)
    version = str(release_data.get("VERSION_ID", "")).strip()
    variant = str(release_data.get("VARIANT", "")).strip()
    if not variant:
        variant = SystemManager.get_variant_name()
    package_manager = "rpm-ostree" if is_atomic else "dnf"
    deployment_mode = "Atomic" if is_atomic else "Traditional"
    if is_atomic:
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
