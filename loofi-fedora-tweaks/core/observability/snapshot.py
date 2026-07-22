"""Health snapshot model for the v12 My Fedora Today timeline."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Iterable, cast

from core.diagnostics.daily_maintenance import DailyMaintenanceReport, MaintenanceCard
from core.fedora_release_policy import FEDORA_RELEASE_POLICY
from core.observability.fingerprints import ProblemFingerprint, fingerprints_from_cards
from core.observability.privacy import redact_payload
from services.system.system import SystemManager
from version import __version__, __version_codename__

SNAPSHOT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class HealthSnapshot:
    """A bounded, privacy-safe health snapshot."""

    timestamp: float
    app_version: str
    app_codename: str
    fedora_target: str
    atomic: bool
    daily_maintenance: dict[str, Any]
    action_center_summary: dict[str, Any]
    failed_service_fingerprints: list[ProblemFingerprint] = field(default_factory=list)
    journal_warning_fingerprints: list[ProblemFingerprint] = field(default_factory=list)
    disk_usage_summary: dict[str, Any] = field(default_factory=dict)
    package_manager_health_summary: dict[str, Any] = field(default_factory=dict)
    rollback_snapshot_availability: dict[str, Any] = field(default_factory=dict)
    problem_fingerprints: list[ProblemFingerprint] = field(default_factory=list)
    collection_errors: list[str] = field(default_factory=list)
    schema_version: int = SNAPSHOT_SCHEMA_VERSION

    @classmethod
    def from_daily_maintenance(
        cls,
        report: DailyMaintenanceReport,
        *,
        action_center_items: Iterable[Any] | None = None,
        fedora_target: str = FEDORA_RELEASE_POLICY.stable_target,
        timestamp: float | None = None,
    ) -> "HealthSnapshot":
        cards = list(report.cards)
        card_map = {card.id: card for card in cards}
        action_items = list(action_center_items or [])
        fingerprints = fingerprints_from_cards(cards)
        failed = [item for item in fingerprints if item.kind == "failed-service"]
        journal = [item for item in fingerprints if item.kind == "journal-warning"]
        return cls(
            timestamp=timestamp or report.generated_at or time.time(),
            app_version=__version__,
            app_codename=__version_codename__,
            fedora_target=fedora_target,
            atomic=report.atomic,
            daily_maintenance=redact_payload(report.to_dict()),
            action_center_summary={
                "candidate_count": len(action_items),
                "by_risk": _count_by(action_items, "risk_level"),
                "by_state": _count_by(action_items, "state"),
            },
            failed_service_fingerprints=failed,
            journal_warning_fingerprints=journal,
            disk_usage_summary=_card_summary(card_map.get("disk-usage")),
            package_manager_health_summary=_card_summary(card_map.get("package-health")),
            rollback_snapshot_availability=_card_summary(card_map.get("rollback")),
            problem_fingerprints=fingerprints,
            collection_errors=[],
        )

    @classmethod
    def collect(
        cls,
        *,
        maintenance_service: Any | None = None,
        action_center_service: Any | None = None,
        fedora_target: str = FEDORA_RELEASE_POLICY.stable_target,
    ) -> "HealthSnapshot":
        from core.actions import ActionCenterService
        from core.diagnostics.daily_maintenance import DailyMaintenanceService

        service = maintenance_service or DailyMaintenanceService()
        action_service = action_center_service or ActionCenterService()
        errors: list[str] = []
        try:
            report = service.collect()
        except (OSError, RuntimeError, ValueError, TypeError) as exc:  # pragma: no cover - defensive GUI/daemon boundary
            report = DailyMaintenanceReport(generated_at=time.time(), atomic=SystemManager.is_atomic(), cards=[], recommended_action="Collection failed.")
            errors.append(str(exc))
        try:
            action_items = action_service.candidates_from_readiness(fedora_target)
        except (OSError, RuntimeError, ValueError, TypeError) as exc:  # pragma: no cover - defensive GUI/daemon boundary
            action_items = []
            errors.append(str(exc))
        snapshot = cls.from_daily_maintenance(report, action_center_items=action_items, fedora_target=fedora_target)
        return cls(
            **{
                **snapshot.__dict__,
                "collection_errors": [str(item) for item in errors],
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HealthSnapshot":
        return cls(
            timestamp=float(data.get("timestamp", 0.0)),
            app_version=str(data.get("app_version", "")),
            app_codename=str(data.get("app_codename", "")),
            fedora_target=str(data.get("fedora_target", FEDORA_RELEASE_POLICY.stable_target)),
            atomic=bool(data.get("atomic", False)),
            daily_maintenance=dict(data.get("daily_maintenance", {}) if isinstance(data.get("daily_maintenance", {}), dict) else {}),
            action_center_summary=dict(data.get("action_center_summary", {}) if isinstance(data.get("action_center_summary", {}), dict) else {}),
            failed_service_fingerprints=_fingerprints(data.get("failed_service_fingerprints", [])),
            journal_warning_fingerprints=_fingerprints(data.get("journal_warning_fingerprints", [])),
            disk_usage_summary=dict(data.get("disk_usage_summary", {}) if isinstance(data.get("disk_usage_summary", {}), dict) else {}),
            package_manager_health_summary=dict(
                data.get("package_manager_health_summary", {}) if isinstance(data.get("package_manager_health_summary", {}), dict) else {}
            ),
            rollback_snapshot_availability=dict(
                data.get("rollback_snapshot_availability", {}) if isinstance(data.get("rollback_snapshot_availability", {}), dict) else {}
            ),
            problem_fingerprints=_fingerprints(data.get("problem_fingerprints", [])),
            collection_errors=[str(item) for item in data.get("collection_errors", []) if item],
            schema_version=int(data.get("schema_version", SNAPSHOT_SCHEMA_VERSION)),
        )

    def to_dict(self, *, privacy_safe: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "timestamp": self.timestamp,
            "app_version": self.app_version,
            "app_codename": self.app_codename,
            "fedora_target": self.fedora_target,
            "atomic": self.atomic,
            "daily_maintenance": self.daily_maintenance,
            "action_center_summary": self.action_center_summary,
            "failed_service_fingerprints": [item.to_dict() for item in self.failed_service_fingerprints],
            "journal_warning_fingerprints": [item.to_dict() for item in self.journal_warning_fingerprints],
            "disk_usage_summary": self.disk_usage_summary,
            "package_manager_health_summary": self.package_manager_health_summary,
            "rollback_snapshot_availability": self.rollback_snapshot_availability,
            "problem_fingerprints": [item.to_dict() for item in self.problem_fingerprints],
            "collection_errors": list(self.collection_errors),
        }
        return cast(dict[str, Any], redact_payload(payload)) if privacy_safe else payload


def _card_summary(card: MaintenanceCard | None) -> dict[str, Any]:
    if card is None:
        return {}
    return cast(
        dict[str, Any],
        redact_payload(
            {
                "id": card.id,
                "state": card.state,
                "summary": card.summary,
                "details": card.details,
                "command_preview": list(card.command_preview),
                "requires_package": card.requires_package,
            }
        ),
    )


def _count_by(items: Iterable[Any], attr: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(getattr(item, attr, "") or "")
        if value:
            counts[value] = counts.get(value, 0) + 1
    return counts


def _fingerprints(value: Any) -> list[ProblemFingerprint]:
    if not isinstance(value, list):
        return []
    return [ProblemFingerprint.from_dict(item) for item in value if isinstance(item, dict)]
