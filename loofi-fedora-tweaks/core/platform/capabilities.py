"""Traditional/Atomic parity records for exposed mutating action families."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Support = Literal["supported", "read-only", "unsupported"]


@dataclass(frozen=True)
class ActionCapability:
    action: str
    traditional: Support
    atomic: Support
    atomic_alternative: str
    confirmation: bool = True
    timeout_required: bool = True
    verification_required: bool = True
    rollback_guidance: str = "Review the action-specific rollback guidance before applying changes."


ACTION_CAPABILITIES = {
    item.action: item for item in (
        ActionCapability("package.install", "supported", "supported", "Layer packages with rpm-ostree or use Flatpak."),
        ActionCapability("package.remove", "supported", "supported", "Remove layered packages with rpm-ostree."),
        ActionCapability("package.update", "supported", "supported", "Stage an rpm-ostree upgrade and reboot."),
        ActionCapability("maintenance.autoremove", "supported", "unsupported", "Atomic base packages are image-managed; remove unused Flatpaks instead."),
        ActionCapability("maintenance.clean-cache", "supported", "read-only", "Inspect cache usage; do not mutate the immutable base."),
        ActionCapability("service.manage", "supported", "supported", "Systemd service management is deployment-independent."),
        ActionCapability("firewall.manage", "supported", "supported", "Firewalld changes use the same Polkit boundary."),
        ActionCapability("snapshot.create", "supported", "supported", "Use rpm-ostree deployments as the base-system rollback mechanism."),
        ActionCapability("state.restore", "supported", "supported", "Loofi user state is independent of the immutable base."),
        ActionCapability("firmware.update", "supported", "supported", "Use fwupd after explicit preview and confirmation."),
    )
}


def capability_for(action: str, *, atomic: bool) -> tuple[Support, str]:
    capability = ACTION_CAPABILITIES[action]
    support = capability.atomic if atomic else capability.traditional
    reason = capability.atomic_alternative if atomic and support != "supported" else "Supported with preview, confirmation, timeout, verification, and rollback guidance."
    return support, reason
