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
    _catalog_operation("cli:changes apply", "mutating", verification="separate action-center verify command"),
    _plan(
        "cli:activity recover",
        "recovery",
        "dnf5-history-undo",
        "rpm-ostree-rollback",
        verification="transaction or deployment readback",
        alias="activity recovery compatibility command",
    ),
    _manual("cli:updates schedule", "updates", "schedule-system-update", guidance="Review timer, package-manager, and reboot behavior."),
    _manual("cli:updates rollback", "updates", "rollback-latest-update", guidance="Select an exact transaction or deployment first."),
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
