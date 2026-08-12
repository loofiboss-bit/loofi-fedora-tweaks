"""Fail-closed eligibility derived from canonical Action Center metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Literal, Mapping

from core.actions.contracts import ActionDefinition

EligibilityKind = Literal["direct", "confirmation", "review_required", "blocked"]
_VALID_RISKS = frozenset({"low", "medium", "high"})
_VALID_OPERATION_CLASSES = frozenset({"host", "app_state", "session", "manual_only"})
_VALID_VARIANTS = frozenset({"traditional", "atomic"})
_VALID_REBOOT_POLICIES = frozenset({"none", "may_require", "required"})


@dataclass(frozen=True)
class EligibilityDecision:
    """Machine-readable direct-action policy classification."""

    action_id: str
    kind: EligibilityKind
    allowed: bool
    reason_code: str
    explanation: str
    risk_level: str = "unknown"
    confirmation_required: bool = False
    metadata_complete: bool = False
    manual_only: bool = False
    supported_variants: tuple[str, ...] = ()
    facts: dict[str, Any] | None = None

    @property
    def direct_allowed(self) -> bool:
        return self.allowed and self.kind == "direct"

    @property
    def review_required(self) -> bool:
        return self.kind == "review_required"

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "kind": self.kind,
            "allowed": self.allowed,
            "reason_code": self.reason_code,
            "explanation": self.explanation,
            "risk_level": self.risk_level,
            "confirmation_required": self.confirmation_required,
            "metadata_complete": self.metadata_complete,
            "manual_only": self.manual_only,
            "supported_variants": list(self.supported_variants),
            "facts": dict(self.facts or {}),
        }


def classify_definition(definition: ActionDefinition | None, *, action_id: str = "") -> EligibilityDecision:
    """Classify one definition without probing or executing the host.

    The function deliberately does not maintain a second executable-action
    allow-list. The Action Center definition is the source of truth; missing or
    malformed metadata can only lower authority to review/blocked.
    """
    requested_id = str(action_id or getattr(definition, "id", "") or "")
    if definition is None:
        return EligibilityDecision(
            requested_id,
            "blocked",
            False,
            "unknown_action",
            "The action is not registered in the Action Center catalog.",
        )

    issues = _metadata_issues(definition)
    variants = tuple(sorted(str(item) for item in definition.supported_variants))
    common: dict[str, Any] = {
        "risk_level": str(definition.risk_level),
        "metadata_complete": not issues,
        "manual_only": definition.operation_class == "manual_only",
        "supported_variants": variants,
        "facts": {"metadata_issues": issues} if issues else {},
    }
    if issues:
        return EligibilityDecision(
            definition.id,
            "review_required",
            False,
            "incomplete_action_metadata",
            "The registered action metadata is incomplete; review it in Action Center.",
            **common,
        )
    if definition.operation_class == "manual_only":
        return EligibilityDecision(
            definition.id,
            "review_required",
            False,
            "manual_only_action",
            "This action is guidance-only and cannot run through direct execution.",
            **common,
        )
    if definition.risk_level == "high":
        return EligibilityDecision(
            definition.id,
            "review_required",
            False,
            "high_risk_action",
            "High-risk actions require the full Action Center review flow.",
            **common,
        )
    if definition.risk_level == "medium":
        return EligibilityDecision(
            definition.id,
            "confirmation",
            True,
            "medium_risk_confirmation",
            "This medium-risk action requires one compact confirmation before execution.",
            confirmation_required=True,
            **common,
        )
    return EligibilityDecision(
        definition.id,
        "direct",
        True,
        "low_risk_direct",
        "This low-risk action may run after a fresh Action Center preflight.",
        **common,
    )


def audit_definitions(definitions: Iterable[ActionDefinition]) -> tuple[dict[str, Any], ...]:
    """Return a bounded audit projection for every first-party definition."""
    report: list[dict[str, Any]] = []
    for definition in definitions:
        decision = classify_definition(definition)
        report.append(
            {
                "action_id": definition.id,
                "title": definition.title,
                "risk_level": str(definition.risk_level),
                "operation_class": definition.operation_class,
                "supported_variants": list(decision.supported_variants),
                "kind": decision.kind,
                "metadata_complete": decision.metadata_complete,
                "reason_code": decision.reason_code,
                "facts": dict(decision.facts or {}),
            }
        )
    return tuple(report)


def _metadata_issues(definition: ActionDefinition) -> list[str]:
    """Validate all fields required before direct policy can be elevated."""
    issues: list[str] = []
    if not definition.id or len(definition.id) > 128:
        issues.append("id")
    if not definition.capability_id or len(definition.capability_id) > 128:
        issues.append("capability_id")
    if not definition.title or not definition.description:
        issues.append("presentation")
    if not isinstance(definition.parameter_schema, Mapping):
        issues.append("parameter_schema")
    if str(definition.risk_level) not in _VALID_RISKS:
        issues.append("risk_level")
    if definition.confirmation_policy not in {"explicit", "explicit-no-rollback"}:
        issues.append("confirmation_policy")
    if not definition.recovery_guidance:
        issues.append("recovery_guidance")
    if not isinstance(definition.rollback_supported, bool):
        issues.append("rollback_supported")
    if definition.operation_class not in _VALID_OPERATION_CLASSES:
        issues.append("operation_class")
    variants = set(str(item) for item in definition.supported_variants)
    if not variants or not variants.issubset(_VALID_VARIANTS):
        issues.append("supported_variants")
    if definition.reboot_policy not in _VALID_REBOOT_POLICIES:
        issues.append("reboot_policy")
    if not definition.affected_resources or len(definition.affected_resources) > 32:
        issues.append("affected_resources")
    if not callable(definition.command_renderer):
        issues.append("command_renderer")
    if not callable(definition.preflight_checker):
        issues.append("preflight_checker")
    if not callable(definition.verifier):
        issues.append("verifier")
    return sorted(set(issues))
