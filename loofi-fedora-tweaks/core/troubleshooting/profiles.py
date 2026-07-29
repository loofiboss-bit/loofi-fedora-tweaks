"""Closed troubleshooting profile catalog and exact collection budgets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping

from core.troubleshooting.validation import (
    MAX_PARAMETERS,
    freeze_mapping,
    thaw,
    validate_application_identifier,
    validate_identifier,
)


PROFILE_VERSION = 1
ProfileAvailability = Literal["available", "reduced"]
SupportedVariant = Literal["traditional", "atomic"]


@dataclass(frozen=True)
class SourceBudget:
    """One exact, variant-aware read-only collection budget."""

    source_id: str
    timeout_seconds: float
    required: bool = True
    variants: frozenset[SupportedVariant] = frozenset({"traditional", "atomic"})

    def __post_init__(self) -> None:
        validate_identifier(self.source_id, field="source_id")
        if self.timeout_seconds <= 0:
            raise ValueError("Every source budget must be positive.")
        if not self.variants or not self.variants.issubset({"traditional", "atomic"}):
            raise ValueError("Every source budget requires valid Fedora variants.")


@dataclass(frozen=True)
class TroubleshootingProfile:
    """One closed symptom profile without collector or execution behavior."""

    id: str
    title: str
    source_budgets: tuple[SourceBudget, ...]
    total_budget_seconds: float
    parameter_schema: tuple[tuple[str, str], ...] = ()
    availability: ProfileAvailability = "available"
    limitation_reason_code: str = ""
    version: int = PROFILE_VERSION

    def __post_init__(self) -> None:
        validate_identifier(self.id, field="profile_id")
        if self.version != PROFILE_VERSION:
            raise ValueError("Unsupported troubleshooting profile version.")
        source_ids = tuple(item.source_id for item in self.source_budgets)
        if not source_ids or len(source_ids) != len(set(source_ids)):
            raise ValueError("A troubleshooting profile requires unique sources.")
        exact_total = max(
            sum(
                item.timeout_seconds
                for item in self.source_budgets
                if variant in item.variants
            )
            for variant in ("traditional", "atomic")
        )
        if self.total_budget_seconds != exact_total:
            raise ValueError("The profile total budget must equal its exact source budgets.")
        parameter_names = tuple(name for name, _kind in self.parameter_schema)
        if len(parameter_names) != len(set(parameter_names)):
            raise ValueError("Troubleshooting profile parameters must be unique.")
        if self.availability == "reduced" and not self.limitation_reason_code:
            raise ValueError("A reduced profile requires a stable limitation reason.")
        if self.availability == "available" and self.limitation_reason_code:
            raise ValueError("An available profile cannot declare a limitation.")

    def budget_for(self, source_id: str, variant: SupportedVariant) -> SourceBudget | None:
        return next(
            (
                budget
                for budget in self.source_budgets
                if budget.source_id == source_id and variant in budget.variants
            ),
            None,
        )

    def required_sources(self, variant: SupportedVariant) -> tuple[str, ...]:
        return tuple(
            budget.source_id
            for budget in self.source_budgets
            if budget.required and variant in budget.variants
        )

    def validate_parameters(self, parameters: Mapping[str, Any] | None) -> tuple[tuple[str, Any], ...]:
        payload = dict(parameters or {})
        if len(payload) > MAX_PARAMETERS:
            raise ValueError("Troubleshooting parameters exceed the bounded limit.")
        schema = dict(self.parameter_schema)
        unknown = sorted(set(payload) - set(schema))
        if unknown:
            raise ValueError(f"Unknown troubleshooting parameters: {', '.join(unknown)}.")
        for name, kind in schema.items():
            if name not in payload:
                raise ValueError(f"Missing required troubleshooting parameter: {name}.")
            if kind == "application_id":
                if not isinstance(payload[name], str):
                    raise ValueError("application_id must be a string.")
                payload[name] = validate_application_identifier(payload[name])
            else:
                raise ValueError(f"Unsupported troubleshooting parameter type: {kind}.")
        return freeze_mapping(payload, field="profile_parameters", max_items=MAX_PARAMETERS)

    def parameters_dict(self, parameters: tuple[tuple[str, Any], ...]) -> dict[str, Any]:
        return dict(thaw(parameters))


_ALL_VARIANTS: frozenset[SupportedVariant] = frozenset({"traditional", "atomic"})
_TRADITIONAL: frozenset[SupportedVariant] = frozenset({"traditional"})
_ATOMIC: frozenset[SupportedVariant] = frozenset({"atomic"})

_PROFILES = (
    TroubleshootingProfile(
        "system_slow",
        "System feels slow",
        (
            SourceBudget("system-check", 45.0),
            SourceBudget("observability", 2.0),
            SourceBudget("change-journal", 15.0),
        ),
        62.0,
    ),
    TroubleshootingProfile(
        "updates_failed",
        "Updates failed",
        (
            SourceBudget("package-health", 20.0, variants=_TRADITIONAL),
            SourceBudget("deployment-state", 20.0, variants=_ATOMIC),
            SourceBudget("pending-reboot", 20.0),
            SourceBudget("change-journal", 15.0),
            SourceBudget("action-center", 10.0),
        ),
        65.0,
    ),
    TroubleshootingProfile(
        "application_failed",
        "An application will not start",
        (
            SourceBudget("application-inventory", 20.0),
            SourceBudget("change-journal", 15.0),
        ),
        35.0,
        parameter_schema=(("application_id", "application_id"),),
        availability="reduced",
        limitation_reason_code="application-journal-collector-unavailable",
    ),
    TroubleshootingProfile(
        "network_problem",
        "Network is not working correctly",
        (
            SourceBudget("network-state", 5.0),
            SourceBudget("dns-state", 5.0),
            SourceBudget("change-journal", 15.0, required=False),
        ),
        25.0,
        availability="reduced",
        limitation_reason_code="network-scan-excluded",
    ),
    TroubleshootingProfile(
        "storage_pressure",
        "Storage is low or filling up",
        (
            SourceBudget("system-check", 45.0),
            SourceBudget("storage-reclaim", 25.0),
            SourceBudget("change-journal", 15.0),
        ),
        85.0,
    ),
    TroubleshootingProfile(
        "boot_or_deployment",
        "Boot, kernel, or deployment problem",
        (
            SourceBudget("boot-analysis", 30.0),
            SourceBudget("failed-services", 10.0),
            SourceBudget("pending-reboot", 20.0),
            SourceBudget("deployment-history", 15.0, variants=_ATOMIC),
            SourceBudget("package-history", 15.0, variants=_TRADITIONAL),
        ),
        75.0,
    ),
)

_PROFILE_BY_ID = {profile.id: profile for profile in _PROFILES}


def all_profiles() -> tuple[TroubleshootingProfile, ...]:
    return _PROFILES


def get_profile(profile_id: str) -> TroubleshootingProfile | None:
    return _PROFILE_BY_ID.get(profile_id)


def require_profile(profile_id: str) -> TroubleshootingProfile:
    profile = get_profile(profile_id)
    if profile is None:
        raise ValueError(f"Unknown troubleshooting profile: {profile_id}.")
    return profile
