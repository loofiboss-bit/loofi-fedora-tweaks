"""Deny-by-default resolution from persisted findings to Action Center reviews."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from core.actions.catalog import ActionCatalog
from core.actions.contracts import FindingContext
from core.observability.timeline import HealthTimelineStore
from core.system_check.mappings import mapped_action, validate_finding
from core.system_check.models import SystemFinding


class FindingHandoffError(ValueError):
    """Stable rejection raised before any Action Center plan is created."""

    def __init__(self, reason_code: str, message: str):
        super().__init__(message)
        self.reason_code = reason_code


@dataclass(frozen=True)
class FindingActionReview:
    """Trusted action and parameters reconstructed from one current finding."""

    action_id: str
    parameters: tuple[tuple[str, Any], ...]
    context: FindingContext

    def parameters_dict(self) -> dict[str, Any]:
        return dict(self.parameters)


def evidence_digest(finding: SystemFinding) -> str:
    """Digest privacy-safe normalized evidence independently of presentation."""
    canonical = json.dumps(
        finding.evidence.to_dict(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class FindingActionHandoff:
    """Resolve only the latest persisted, fresh, mapped System Check finding."""

    def __init__(
        self,
        *,
        snapshot_store: HealthTimelineStore | None = None,
        catalog: ActionCatalog | None = None,
    ) -> None:
        self.snapshot_store = snapshot_store or HealthTimelineStore()
        self.catalog = catalog or ActionCatalog()

    def resolve(
        self,
        *,
        check_result_id: str,
        finding_fingerprint: str,
        origin_route: str,
    ) -> FindingActionReview:
        try:
            origin_context = FindingContext(
                check_result_id=str(check_result_id),
                finding_fingerprint=str(finding_fingerprint),
                evidence_digest="0" * 64,
                origin_route=str(origin_route),
            )
        except ValueError as exc:
            raise FindingHandoffError("invalid_finding_context", str(exc)) from exc

        snapshots = self.snapshot_store.load()
        if self.snapshot_store.last_error:
            raise FindingHandoffError(
                "finding_store_unavailable",
                "Saved System Check results are unavailable.",
            )
        payload = next(
            (
                candidate
                for snapshot in reversed(snapshots)
                if (
                    isinstance(snapshot.daily_maintenance, dict)
                    and isinstance(
                        candidate := snapshot.daily_maintenance.get("system_check"),
                        dict,
                    )
                    and int(candidate.get("schema_version", 0)) == 1
                )
            ),
            None,
        )
        if payload is None:
            raise FindingHandoffError(
                "finding_not_found",
                "No saved System Check finding is available for review.",
            )
        if str(payload.get("check_id", "")) != origin_context.check_result_id:
            raise FindingHandoffError(
                "stale_finding_context",
                "The finding is no longer from the latest saved System Check.",
            )
        if str(payload.get("state", "")) not in {"completed", "partial"}:
            raise FindingHandoffError(
                "non_terminal_finding_context",
                "Only a completed System Check can create an action review.",
            )

        raw_findings = payload.get("findings", [])
        matches = [
            item
            for item in raw_findings
            if (
                isinstance(item, dict)
                and str(item.get("fingerprint", ""))
                == origin_context.finding_fingerprint
            )
        ] if isinstance(raw_findings, list) else []
        if len(matches) != 1:
            raise FindingHandoffError(
                "finding_not_found",
                "The exact saved finding could not be resolved.",
            )
        try:
            finding = SystemFinding.from_dict(matches[0])
            validate_finding(finding, self.catalog)
        except (TypeError, ValueError) as exc:
            raise FindingHandoffError(
                "invalid_finding_context",
                "The saved finding failed integrity validation.",
            ) from exc
        if finding.freshness_state != "fresh":
            raise FindingHandoffError(
                "stale_finding_context",
                "Stale or unavailable evidence cannot create an action review.",
            )

        action_id, parameters = mapped_action(
            finding.finding_id,
            finding.evidence.facts_dict(),
            atomic=bool(payload.get("atomic", False)),
            catalog=self.catalog,
        )
        if (
            not action_id
            or action_id != finding.action_id
            or parameters != finding.parameters_dict()
        ):
            raise FindingHandoffError(
                "finding_mapping_rejected",
                "This finding has no current audited Action Center mapping.",
            )
        context = FindingContext(
            check_result_id=origin_context.check_result_id,
            finding_fingerprint=finding.fingerprint,
            evidence_digest=evidence_digest(finding),
            origin_route=origin_context.origin_route,
            affected_resources=finding.affected_resources,
        )
        return FindingActionReview(
            action_id=action_id,
            parameters=tuple(sorted(parameters.items())),
            context=context,
        )
