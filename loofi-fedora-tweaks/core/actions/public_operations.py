"""Machine-readable public host-mutation inventory.

Operation IDs use the stable ``cli:<command>`` and ``api:<METHOD> <path>``
forms. Operations absent from the override table are host-read-only. This
keeps parser and route registration authoritative while making every host
mutation exception explicit and reviewable here.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterable, Literal, Mapping

PublicOperationClass = Literal["read_only", "plan_only", "manual_only", "mutating"]


@dataclass(frozen=True)
class PublicOperation:
    """Host-effect classification for one public CLI command or API endpoint."""

    operation_id: str
    classification: PublicOperationClass
    domain_owner: str
    action_definition_ids: tuple[str, ...] = ()
    privilege_requirement: str = "none"
    traditional_behavior: str = "No direct host mutation."
    atomic_behavior: str = "No direct host mutation."
    confirmation_requirement: str = "none"
    verification_method: str = "not_applicable"
    recovery_guidance: str = "No host recovery is required."
    compatibility_alias: str | None = None
    direct_host_mutation: bool = False
    catalog_bound: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "operation_id": self.operation_id,
            "classification": self.classification,
            "domain_owner": self.domain_owner,
            "action_definition_ids": list(self.action_definition_ids),
            "privilege_requirement": self.privilege_requirement,
            "traditional_behavior": self.traditional_behavior,
            "atomic_behavior": self.atomic_behavior,
            "confirmation_requirement": self.confirmation_requirement,
            "verification_method": self.verification_method,
            "recovery_guidance": self.recovery_guidance,
            "compatibility_alias": self.compatibility_alias,
            "direct_host_mutation": self.direct_host_mutation,
            "catalog_bound": self.catalog_bound,
        }


def _plan(
    operation_id: str,
    owner: str,
    *definition_ids: str,
    verification: str,
    traditional: str = "Creates a closed Action Center plan.",
    atomic: str = "Creates a closed Action Center plan.",
    privilege: str = "resolved by the selected Action Center definition",
    recovery: str = "Use the selected Action Center definition's recovery guidance.",
    alias: str | None = None,
) -> PublicOperation:
    return PublicOperation(
        operation_id=operation_id,
        classification="plan_only",
        domain_owner=owner,
        action_definition_ids=tuple(definition_ids),
        privilege_requirement=privilege,
        traditional_behavior=traditional,
        atomic_behavior=atomic,
        confirmation_requirement="separate explicit Action Center apply",
        verification_method=verification,
        recovery_guidance=recovery,
        compatibility_alias=alias,
    )


def _manual(
    operation_id: str,
    owner: str,
    definition_id: str | None,
    *,
    guidance: str,
    alias: str | None = None,
) -> PublicOperation:
    return PublicOperation(
        operation_id=operation_id,
        classification="manual_only",
        domain_owner=owner,
        action_definition_ids=(definition_id,) if definition_id else (),
        privilege_requirement="none; Loofi does not execute the requested host change",
        traditional_behavior="Creates a blocked, parameter-validated review plan or returns manual guidance.",
        atomic_behavior="Creates a blocked, parameter-validated review plan or returns manual guidance.",
        confirmation_requirement="manual action outside Loofi",
        verification_method="manual readback described by the definition",
        recovery_guidance=guidance,
        compatibility_alias=alias,
    )


def _catalog_operation(
    operation_id: str,
    classification: PublicOperationClass,
    *,
    verification: str,
) -> PublicOperation:
    return PublicOperation(
        operation_id=operation_id,
        classification=classification,
        domain_owner="Action Center",
        privilege_requirement="resolved by the selected digest-bound plan",
        traditional_behavior="Uses only the selected closed catalog definition.",
        atomic_behavior="Uses only the selected closed catalog definition and variant policy.",
        confirmation_requirement="explicit confirmation of an existing plan",
        verification_method=verification,
        recovery_guidance="Use the selected plan's persisted recovery guidance.",
        catalog_bound=True,
    )


_OVERRIDES = [
    PublicOperation(
        operation_id="cli:self-update check",
        classification="read_only",
        domain_owner="self-update",
        traditional_behavior="Checks signed release metadata without installing or changing packages.",
        atomic_behavior="Checks signed release metadata without installing or changing deployments.",
        verification_method="release metadata and selected artifact identity",
    ),
    PublicOperation(
        operation_id="cli:self-update run",
        classification="read_only",
        domain_owner="self-update",
        traditional_behavior="Downloads and verifies an artifact to the user-selected path; never installs it.",
        atomic_behavior="Downloads and verifies an artifact to the user-selected path; never layers or deploys it.",
        verification_method="artifact checksum and optional signature verification",
        recovery_guidance="Delete the downloaded artifact if it is no longer needed.",
    ),
    _plan("cli:cleanup all", "maintenance", "dnf-clean-all", "vacuum-journal", "fstrim-all", verification="each definition verifier"),
    _plan("cli:cleanup dnf", "maintenance", "dnf-clean-all", verification="repository and package health readback"),
    _plan("cli:cleanup journal", "maintenance", "vacuum-journal", verification="journal retention readback"),
    _plan("cli:cleanup trim", "storage", "fstrim-all", verification="validated filesystem trim output"),
    _plan(
        "cli:cleanup autoremove",
        "packages",
        "autoremove-packages",
        verification="installed-package readback",
        atomic="Blocked by the definition's Traditional-only variant policy.",
    ),
    _manual("cli:cleanup rpmdb", "packages", None, guidance="Use Troubleshooting to inspect RPM database health."),
    _manual("cli:tweak power", "power", "set-power-profile", guidance="Verify the selected power profile.", alias="legacy tweak power"),
    _manual("cli:tweak audio", "audio", "restart-audio-session", guidance="Verify the user audio session.", alias="legacy tweak audio"),
    _manual("cli:tweak battery", "power", "set-battery-limit", guidance="Verify hardware support and the selected limit.", alias="legacy tweak battery"),
    _manual("cli:advanced dnf-tweaks", "packages", "optimize-dnf-config", guidance="Review existing DNF5 configuration."),
    _manual("cli:advanced bbr", "network", "enable-tcp-bbr", guidance="Verify kernel support and retain previous sysctl values."),
    _manual("cli:advanced gamemode", "packages", "install-gamemode", guidance="Review package and group changes."),
    _manual("cli:advanced swappiness", "performance", "set-swappiness", guidance="Retain and verify the current sysctl value."),
    _manual("cli:network dns", "network", "configure-network-dns", guidance="Verify the exact connection-scoped resolver state."),
    _plan(
        "cli:activity recover",
        "recovery",
        "dnf5-history-undo",
        "rpm-ostree-rollback",
        verification="transaction or deployment readback",
        alias="activity recovery compatibility command",
    ),
    _plan(
        "cli:readiness action-run",
        "release readiness",
        "dnf-clean-all",
        verification="repository and package health readback",
        alias="readiness-repo-cache-clean",
    ),
    _catalog_operation("cli:action-center plan", "plan_only", verification="selected definition verifier"),
    _catalog_operation("cli:action-center apply", "mutating", verification="separate action-center verify command"),
    _catalog_operation(
        "api:POST /api/action-center/plans",
        "plan_only",
        verification="selected definition verifier",
    ),
    _manual("cli:preset apply", "profiles", "local-profile-review", guidance="Review each profile setting in its owning workflow."),
    _manual("cli:focus-mode on", "focus mode", "control-focus-mode", guidance="Review hosts, process, and desktop-session effects."),
    _manual("cli:focus-mode off", "focus mode", "control-focus-mode", guidance="Review hosts restoration and desktop-session effects."),
    _manual("cli:profile apply", "profiles", "apply-system-profile", guidance="Review every profile-owned host setting."),
    _manual("cli:tuner apply", "performance", "apply-performance-tuning", guidance="Retain and verify each current tuning value."),
    _plan("cli:snapshot create", "recovery", "create-recovery-point", verification="backend recovery-point readback"),
    _manual("cli:snapshot delete", "recovery", "delete-recovery-point", guidance="Verify the exact backend and recovery point."),
    *[
        _manual(
            f"cli:service {action}",
            "services",
            "service-control",
            guidance="Inspect the exact unit state and journal before changing it.",
        )
        for action in ("start", "stop", "restart", "enable", "disable", "mask", "unmask")
    ],
    _plan("cli:package install", "applications", "install-application", verification="package or Flatpak installation readback"),
    _plan("cli:package remove", "applications", "remove-application", verification="package or Flatpak absence readback"),
    _manual("cli:firewall open-port", "firewall", "allow-firewall-port", guidance="Verify the selected port, protocol, and zone."),
    _manual("cli:firewall close-port", "firewall", "block-firewall-port", guidance="Verify the selected port, protocol, and zone."),
    _manual(
        "cli:firewall add-service",
        "firewall",
        "firewall-service-control",
        guidance="Verify the selected service and zone.",
        alias="handler compatibility operation",
    ),
    _manual(
        "cli:firewall remove-service",
        "firewall",
        "firewall-service-control",
        guidance="Verify the selected service and zone.",
        alias="handler compatibility operation",
    ),
    _manual(
        "cli:firewall set-default-zone",
        "firewall",
        "set-firewall-default-zone",
        guidance="Verify active interfaces and the selected zone.",
        alias="handler compatibility operation",
    ),
    _manual(
        "cli:firewall reload",
        "firewall",
        "reload-firewall",
        guidance="Review permanent and runtime rules before reloading.",
        alias="handler compatibility operation",
    ),
    *[
        _manual(
            f"cli:bluetooth {action}",
            "bluetooth",
            "control-bluetooth-device",
            guidance="Use the system Bluetooth controls and verify the exact device state.",
        )
        for action in ("power-on", "power-off", "connect", "disconnect", "pair", "unpair", "trust")
    ],
    _manual("cli:vm start", "virtualization", "control-virtual-machine", guidance="Verify the exact virtual machine state."),
    _manual("cli:vm stop", "virtualization", "control-virtual-machine", guidance="Verify the exact virtual machine state."),
    _manual(
        "cli:teleport restore",
        "workspace portability",
        None,
        guidance="Inspect the saved package and restore the workspace manually.",
    ),
    _plan("cli:storage trim", "storage", "fstrim-all", verification="validated filesystem trim output"),
    _manual("cli:updates schedule", "updates", "schedule-system-update", guidance="Review timer, package-manager, and reboot behavior."),
    _manual("cli:updates rollback", "updates", "rollback-latest-update", guidance="Select an exact transaction or deployment first."),
    *[
        _manual(
            f"cli:extension {action}",
            "desktop extensions",
            f"{action}-desktop-extension",
            guidance="Use the desktop extension manager and verify the exact extension state.",
        )
        for action in ("install", "remove", "enable", "disable")
    ],
    _plan(
        "cli:flatpak-manage install",
        "applications",
        "install-application",
        verification="Flatpak installation readback",
        alias="handler compatibility operation",
    ),
    _plan(
        "cli:flatpak-manage uninstall",
        "applications",
        "remove-application",
        verification="Flatpak absence readback",
        alias="handler compatibility operation",
    ),
    _manual(
        "cli:flatpak-manage update",
        "applications",
        "update-flatpak-application",
        guidance="Review the exact application or use the canonical full Flatpak update plan.",
        alias="handler compatibility operation",
    ),
    _manual(
        "cli:flatpak-manage cleanup",
        "applications",
        "remove-unused-flatpaks",
        guidance="Review the exact unused runtime set manually.",
    ),
    _manual("cli:boot timeout", "boot", "set-grub-timeout", guidance="Retain a tested boot recovery path."),
    _manual("cli:boot apply", "boot", "apply-grub-config", guidance="Retain recovery media and verify boot configuration."),
    _manual("cli:display fractional-on", "display", "set-fractional-scaling", guidance="Verify the Plasma display configuration."),
    _manual("cli:display fractional-off", "display", "set-fractional-scaling", guidance="Verify the Plasma display configuration."),
    _plan("cli:backup create", "recovery", "create-recovery-point", verification="backend recovery-point readback"),
    _manual("cli:backup restore", "recovery", "restore-recovery-point", guidance="Verify the exact backend and recovery point."),
    _manual("cli:backup delete", "recovery", "delete-recovery-point", guidance="Verify the exact backend and recovery point."),
]

PUBLIC_OPERATION_OVERRIDES: Mapping[str, PublicOperation] = MappingProxyType(
    {item.operation_id: item for item in _OVERRIDES}
)


def public_operation(operation_id: str) -> PublicOperation:
    """Return one explicit override or the default host-read-only record."""
    normalized = str(operation_id)
    if not normalized.startswith(("cli:", "api:")):
        raise ValueError(f"Unsupported public operation ID: {normalized}")
    return PUBLIC_OPERATION_OVERRIDES.get(
        normalized,
        PublicOperation(
            operation_id=normalized,
            classification="read_only",
            domain_owner="public interface",
        ),
    )


def public_operation_inventory(operation_ids: Iterable[str]) -> tuple[PublicOperation, ...]:
    """Classify a stable parser/route-derived operation set."""
    return tuple(public_operation(operation_id) for operation_id in sorted(set(operation_ids)))


def validate_public_operation_inventory(
    operation_ids: Iterable[str],
    *,
    known_action_ids: Iterable[str],
) -> list[str]:
    """Return coverage, definition, and direct-host-mutation errors."""
    known_operations = set(operation_ids)
    known_definitions = set(known_action_ids)
    errors: list[str] = []
    for operation_id in sorted(set(PUBLIC_OPERATION_OVERRIDES) - known_operations):
        if PUBLIC_OPERATION_OVERRIDES[operation_id].compatibility_alias is None:
            errors.append(f"public operation override has no parser or route: {operation_id}")
    for item in public_operation_inventory(known_operations):
        if item.direct_host_mutation:
            errors.append(f"public operation directly mutates the host: {item.operation_id}")
        if item.classification in {"plan_only", "manual_only"} and not (
            item.action_definition_ids
            or item.classification == "manual_only"
            or item.catalog_bound
        ):
            errors.append(f"public operation has no Action Center definition or manual guidance: {item.operation_id}")
        for action_id in item.action_definition_ids:
            if action_id not in known_definitions:
                errors.append(f"public operation references unknown Action Center definition: {item.operation_id} -> {action_id}")
        if item.classification == "mutating" and not item.catalog_bound:
            errors.append(f"mutating public operation is outside Action Center: {item.operation_id}")
    return errors
