"""Symptom-first Fix workflow metadata and safe next-step projection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Sequence

from core.troubleshooting.profiles import TroubleshootingProfile, require_profile


FixPhase = Literal["choose_symptom", "collecting", "findings", "repair", "recovery"]
RepairKind = Literal["action", "navigation", "manual", "none"]


@dataclass(frozen=True)
class FixSymptom:
    """A user-observable symptom mapped to one closed diagnostic profile."""

    id: str
    title: str
    description: str
    profile_id: str
    keywords: tuple[str, ...] = ()

    def profile(self) -> TroubleshootingProfile:
        return require_profile(self.profile_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "profile_id": self.profile_id,
            "keywords": list(self.keywords),
        }


@dataclass(frozen=True)
class FixRepairOption:
    """One finding-specific next step; there is deliberately no Fix all."""

    id: str
    label: str
    kind: RepairKind
    target_id: str = ""
    description: str = ""
    verification: str = "Review the result in Activity & Recovery."
    requires_confirmation: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.kind == "action" and not self.target_id:
            raise ValueError("Action repair options need a stable action ID.")
        if self.kind == "navigation" and not self.target_id:
            raise ValueError("Navigation repair options need a canonical route ID.")
        if self.kind in {"manual", "none"} and self.target_id:
            raise ValueError("Manual or empty repair options cannot carry a target.")
        object.__setattr__(self, "metadata", dict(self.metadata))

    @property
    def executable(self) -> bool:
        return self.kind == "action"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "kind": self.kind,
            "target_id": self.target_id,
            "description": self.description,
            "verification": self.verification,
            "requires_confirmation": self.requires_confirmation,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class FixInspectionRequest:
    """Validated request passed from the symptom picker to the read-only worker."""

    symptom: FixSymptom
    parameters: Mapping[str, Any] = field(default_factory=dict)
    phase: FixPhase = "choose_symptom"

    def __post_init__(self) -> None:
        validated = self.symptom.profile().validate_parameters(self.parameters)
        object.__setattr__(self, "parameters", dict(validated))
        if self.phase not in {"choose_symptom", "collecting", "findings", "repair", "recovery"}:
            raise ValueError(f"Unsupported Fix workflow phase: {self.phase}")

    def collecting(self) -> "FixInspectionRequest":
        return FixInspectionRequest(self.symptom, self.parameters, "collecting")

    def findings(self) -> "FixInspectionRequest":
        return FixInspectionRequest(self.symptom, self.parameters, "findings")

    def to_dict(self) -> dict[str, Any]:
        return {
            "symptom": self.symptom.to_dict(),
            "parameters": dict(self.parameters),
            "phase": self.phase,
        }


_SYMPTOMS: tuple[FixSymptom, ...] = (
    FixSymptom("system-slow", "System feels slow", "Measure bounded system and recent-change evidence before a repair.", "system_slow", ("slow", "performance")),
    FixSymptom("updates-failed", "Updates failed", "Inspect package or deployment state before retrying an update.", "updates_failed", ("updates", "packages")),
    FixSymptom("application-failed", "An application will not start", "Inspect the selected application and its recent Activity record.", "application_failed", ("application", "crash", "start")),
    FixSymptom("network-problem", "Network is not working correctly", "Inspect local connection and DNS evidence before opening native settings.", "network_problem", ("network", "wifi", "dns")),
    FixSymptom("storage-pressure", "Storage is low or filling up", "Measure storage pressure and review reclaimable data before cleanup.", "storage_pressure", ("storage", "disk", "space")),
    FixSymptom("boot-or-deployment", "Boot, kernel, or deployment problem", "Inspect bounded boot and deployment evidence before recovery.", "boot_or_deployment", ("boot", "kernel", "deployment")),
)


class FixCatalog:
    """Closed symptom catalog with no aggregate or blind repair operation."""

    def __init__(self, symptoms: Sequence[FixSymptom] | None = None) -> None:
        selected = tuple(symptoms or _SYMPTOMS)
        if not selected:
            raise ValueError("Fix catalog must contain at least one symptom.")
        ids = [item.id for item in selected]
        if len(ids) != len(set(ids)):
            raise ValueError("Fix symptom IDs must be unique.")
        self._symptoms = selected
        self._by_id = {item.id: item for item in selected}

    def symptoms(self) -> tuple[FixSymptom, ...]:
        return self._symptoms

    def get(self, symptom_id: str) -> FixSymptom | None:
        return self._by_id.get(str(symptom_id).strip())

    def search(self, query: str = "") -> tuple[FixSymptom, ...]:
        tokens = tuple(" ".join(str(query).casefold().split()).split())
        return tuple(
            symptom
            for symptom in self._symptoms
            if not tokens or all(token in " ".join((symptom.id, symptom.title, symptom.description, *symptom.keywords)).casefold() for token in tokens)
        )

    def request(self, symptom_id: str, parameters: Mapping[str, Any] | None = None) -> FixInspectionRequest:
        symptom = self.get(symptom_id)
        if symptom is None:
            raise KeyError(f"Unknown Fix symptom: {symptom_id}")
        return FixInspectionRequest(symptom, parameters or {})

    @staticmethod
    def repair_options(*, action_id: str = "", navigation_route: str = "", guidance: str = "") -> tuple[FixRepairOption, ...]:
        """Build finding-specific options while preserving one safe next step."""
        options: list[FixRepairOption] = []
        if action_id:
            options.append(FixRepairOption("verified-repair", "Run verified repair", "action", action_id, verification="Verify the repaired state on this page."))
        if navigation_route:
            options.append(FixRepairOption("open-settings", "Open system settings", "navigation", navigation_route, description="Continue in the native settings surface.", requires_confirmation=False))
        if guidance:
            options.append(FixRepairOption("manual-guidance", "Open instructions", "manual", description=guidance, verification="Return to Fix and run a fresh check."))
        if not options:
            options.append(FixRepairOption("no-safe-repair", "No safe repair available", "none", description="Review the evidence and follow the recovery guidance."))
        return tuple(options[:1])


def all_fix_symptoms() -> tuple[FixSymptom, ...]:
    """Return the closed symptom set used by Fix."""

    return FixCatalog().symptoms()


__all__ = [
    "FixCatalog",
    "FixInspectionRequest",
    "FixPhase",
    "FixRepairOption",
    "FixSymptom",
    "RepairKind",
    "all_fix_symptoms",
]
