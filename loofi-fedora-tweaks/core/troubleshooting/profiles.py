"""Closed troubleshooting profile catalog and exact collection budgets."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal, Mapping

from core.troubleshooting.validation import (
    MAX_PARAMETERS,
    freeze_mapping,
    thaw,
    validate_application_identifier,
    validate_identifier,
    validate_resource_identifier,
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
        if self.version < 1:
            raise ValueError("Troubleshooting profile versions must be positive.")
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
            if name not in payload and kind in {"optional_run_id", "optional_boolean"}:
                if kind == "optional_boolean":
                    payload[name] = False
                continue
            if name not in payload:
                raise ValueError(f"Missing required troubleshooting parameter: {name}.")
            if kind == "application_id":
                if not isinstance(payload[name], str):
                    raise ValueError("application_id must be a string.")
                payload[name] = validate_application_identifier(payload[name])
            elif kind == "application_identity":
                if not isinstance(payload[name], str):
                    raise ValueError("application_id must be a package name or full Flatpak reference.")
                payload[name] = validate_application_identifier(payload[name], allow_flatpak_ref=True)
            elif kind == "application_scope":
                scope = payload[name]
                if not isinstance(scope, str) or (
                    scope not in {"rpm", "flatpak-user", "flatpak-system"}
                    and _FLATPAK_INSTALLATION.fullmatch(scope) is None
                ):
                    raise ValueError("application_scope must select an exact RPM or Flatpak installation.")
            elif kind == "optional_run_id":
                payload[name] = validate_resource_identifier(payload[name])
                if "/" in payload[name]:
                    raise ValueError("run_id cannot contain a path.")
            elif kind == "optional_boolean":
                if not isinstance(payload[name], bool):
                    raise ValueError(f"{name} must be a boolean.")
            else:
                raise ValueError(f"Unsupported troubleshooting parameter type: {kind}.")
        if schema.get("application_id") == "application_identity":
            identifier = payload["application_id"]
            scope = payload["application_scope"]
            is_flatpak_ref = identifier.startswith("app/")
            if (scope == "rpm") == is_flatpak_ref:
                raise ValueError("Application identity does not match the selected installation type.")
        return freeze_mapping(payload, field="profile_parameters", max_items=MAX_PARAMETERS)

    def parameters_dict(self, parameters: tuple[tuple[str, Any], ...]) -> dict[str, Any]:
        return dict(thaw(parameters))


_ALL_VARIANTS: frozenset[SupportedVariant] = frozenset({"traditional", "atomic"})
_TRADITIONAL: frozenset[SupportedVariant] = frozenset({"traditional"})
_ATOMIC: frozenset[SupportedVariant] = frozenset({"atomic"})
_FLATPAK_INSTALLATION = re.compile(r"flatpak-installation:([A-Za-z0-9][A-Za-z0-9._-]{0,127})\Z")

_PROFILES = (
    TroubleshootingProfile(
        "sound_not_working", "Sound is not working",
        (SourceBudget("audio-state", 15.0),), 15.0,
    ),
    TroubleshootingProfile(
        "bluetooth_not_working", "Bluetooth is not working",
        (SourceBudget("bluetooth-state", 15.0),), 15.0,
    ),
    TroubleshootingProfile(
        "screen_sharing_not_working", "Screen sharing is not working",
        (SourceBudget("screen-sharing-state", 15.0),), 15.0,
    ),
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
        parameter_schema=(("run_id", "optional_run_id"),),
    ),
    TroubleshootingProfile(
        "flatpak_updates_failed", "Flatpak updates failed",
        (SourceBudget("flatpak-update-health", 15.0), SourceBudget("action-center", 10.0)),
        25.0, parameter_schema=(("run_id", "optional_run_id"),),
    ),
    TroubleshootingProfile(
        "firmware_updates_failed", "Firmware updates failed",
        (SourceBudget("firmware-update-health", 15.0), SourceBudget("action-center", 10.0)),
        25.0, parameter_schema=(("run_id", "optional_run_id"),),
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

# Existing persisted sessions are validated against the exact collector contract
# they were created with. The active app/network profiles can evolve without
# rewriting that contract or making saved history unreadable.
_LEGACY_PROFILES = {
    (profile.id, profile.version): profile
    for profile in _PROFILES
    if profile.id in {"application_failed", "network_problem"}
}

_ACTIVE_OVERRIDES = {
    "application_failed": TroubleshootingProfile(
        "application_failed",
        "An application will not start",
        (
            SourceBudget("application-inventory", 20.0),
            SourceBudget("application-journal", 15.0),
            SourceBudget("change-journal", 15.0, required=False),
        ),
        50.0,
        parameter_schema=(
            ("application_id", "application_identity"),
            ("application_scope", "application_scope"),
            ("launch_attempted", "optional_boolean"),
        ),
        version=2,
    ),
    "network_problem": TroubleshootingProfile(
        "network_problem",
        "Network is not working correctly",
        (
            SourceBudget("network-state", 10.0),
            SourceBudget("change-journal", 15.0, required=False),
        ),
        25.0,
        version=2,
    ),
}

_HARDWARE_PROFILES = (
    TroubleshootingProfile("battery_problem", "Battery or power problem", (SourceBudget("battery-power", 15.0),), 15.0),
    TroubleshootingProfile("display_problem", "Display or docking problem", (SourceBudget("display-state", 15.0),), 15.0),
    TroubleshootingProfile("input_problem", "Keyboard or touchpad problem", (SourceBudget("input-state", 15.0),), 15.0),
    TroubleshootingProfile("printer_problem", "Printer or print queue problem", (SourceBudget("printer-state", 15.0),), 15.0),
)

_ACTIVE_PROFILES = tuple(
    _ACTIVE_OVERRIDES.get(profile.id, profile) for profile in _PROFILES
) + _HARDWARE_PROFILES
_ACTIVE_PROFILE_BY_ID = {profile.id: profile for profile in _ACTIVE_PROFILES}
_VERSIONED_PROFILE_BY_KEY = {
    **_LEGACY_PROFILES,
    **{(profile.id, profile.version): profile for profile in _ACTIVE_PROFILES},
}


def all_profiles() -> tuple[TroubleshootingProfile, ...]:
    return _ACTIVE_PROFILES


def get_profile(profile_id: str) -> TroubleshootingProfile | None:
    return _ACTIVE_PROFILE_BY_ID.get(profile_id)


def require_profile(profile_id: str, version: int | None = None) -> TroubleshootingProfile:
    profile = (
        get_profile(profile_id)
        if version is None
        else _VERSIONED_PROFILE_BY_KEY.get((profile_id, version))
    )
    if profile is None:
        raise ValueError(f"Unknown troubleshooting profile: {profile_id}.")
    return profile
