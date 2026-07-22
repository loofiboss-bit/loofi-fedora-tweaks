"""Unified Action Center service built on existing readiness and executor layers."""

from __future__ import annotations

import time
from typing import Iterable

from core.actions.history import ActionHistoryStore
from core.actions.model import ActionCenterItem, ActionRisk, ActionState
from core.actions.queue import ActionQueue
from core.actions.rollback import RollbackGuidanceService
from core.diagnostics.readiness_actions import ReadinessActionCandidate, ReadinessActionService
from core.executor.action_result import ActionResult
from core.executor.command_facade import CommandFacade
from core.fedora_release_policy import FEDORA_RELEASE_POLICY


def _normalize_risk(value: str) -> ActionRisk:
    return value if value in {"none", "low", "medium", "high"} else "low"  # type: ignore[return-value]


class ActionCenterService:
    """Preview, queue, execute, verify, and record action candidates."""

    def __init__(
        self,
        *,
        facade: CommandFacade | None = None,
        history: ActionHistoryStore | None = None,
        queue: ActionQueue | None = None,
    ):
        self.facade = facade or CommandFacade()
        self.history = history or ActionHistoryStore()
        self.queue = queue or ActionQueue()

    def candidates_from_readiness(self, target: str = FEDORA_RELEASE_POLICY.stable_target) -> list[ActionCenterItem]:
        plan = ReadinessActionService.build_plan(target)
        return [self.from_readiness_candidate(candidate, target=target) for candidate in plan.candidates]

    def catalog_items(self, target: str = FEDORA_RELEASE_POLICY.stable_target) -> list[ActionCenterItem]:
        """Expose the complete audited v14 catalog without running preflight."""
        from core.actions.catalog import ActionCatalog

        items: list[ActionCenterItem] = []
        for definition in ActionCatalog().list():
            items.append(ActionCenterItem(
                id=definition.id,
                title=definition.title,
                source="catalog:v18",
                description=definition.description,
                risk_level=definition.risk_level,
                privilege="pkexec" if definition.privileged else "none",
                command_preview=[],
                rollback_hint=definition.recovery_guidance,
                manual_only=definition.operation_class == "manual_only",
                confirmation_required=True,
                state="manual_only" if definition.operation_class == "manual_only" else "planned",
                correlation_id=f"catalog:{target}:{definition.id}",
                dedupe_key=f"catalog:{definition.id}",
                safe_next_step="Create a fresh plan to run preflight and generate the exact command.",
                metadata={"catalog": "v18", "target": target},
            ))
        return items

    def recommendations_from_timeline(self, *, limit: int = 30) -> list[ActionCenterItem]:
        """Build deduped, manual-safe recommendations from persisted health trends."""
        from core.observability import HealthTimelineStore, MaintenanceTrendAnalyzer

        snapshots = HealthTimelineStore().load()[-limit:]
        summary = MaintenanceTrendAnalyzer(snapshots).analyze()
        items: dict[str, ActionCenterItem] = {}
        for fingerprint in [*summary.recurring, *summary.new]:
            dedupe_key = f"observability:{fingerprint.id}"
            if dedupe_key in items:
                continue
            risk = "medium" if fingerprint.severity in {"blocked", "error"} else "low"
            items[dedupe_key] = ActionCenterItem(
                id=f"recommendation-{fingerprint.id.replace(':', '-')}",
                title=fingerprint.title,
                source="observability:timeline",
                description=fingerprint.summary,
                risk_level=risk,  # type: ignore[arg-type]
                privilege="none",
                command_preview=[],
                rollback_hint="Review the command preview before any follow-up action.",
                manual_only=True,
                confirmation_required=risk in {"medium", "high"},
                state="manual_only",
                correlation_id=fingerprint.id,
                dedupe_key=dedupe_key,
                why_this_matters=_why_this_matters(fingerprint.kind),
                safe_next_step=_safe_next_step(fingerprint.kind),
                source_snapshot_id=summary.latest_snapshot_id,
                metadata={
                    "fingerprint_id": fingerprint.id,
                    "fingerprint_kind": fingerprint.kind,
                    "snapshot_id": summary.latest_snapshot_id,
                    "group": _recommendation_group(fingerprint.kind),
                },
            )
        return list(items.values())

    def from_readiness_candidate(self, candidate: ReadinessActionCandidate, *, target: str = FEDORA_RELEASE_POLICY.stable_target) -> ActionCenterItem:
        risk = _normalize_risk(candidate.risk_level)
        rollback = RollbackGuidanceService.guidance_for(risk, candidate.revert_hint)
        state: ActionState = "manual_only" if candidate.manual_only else "planned"
        return ActionCenterItem(
            id=candidate.id,
            title=candidate.title,
            source=f"readiness:{target}",
            description=candidate.explanation,
            risk_level=risk,
            privilege="pkexec" if candidate.privileged else "none",
            command_preview=list(candidate.command_preview),
            rollback_hint=rollback.summary,
            rollback_guidance=rollback,
            manual_only=candidate.manual_only,
            confirmation_required=risk in {"medium", "high"},
            verification_command=list(candidate.verification_command),
            state=state,
            correlation_id=f"{candidate.id}-{int(time.time())}",
            dedupe_key=f"readiness:{target}:{candidate.id}",
            why_this_matters=candidate.explanation,
            safe_next_step="Preview this action, review rollback guidance, then run it only if the command and risk match your intent.",
            lifecycle_reason="created",
            metadata={"related_check_id": candidate.related_check_id, "group": "readiness"},
        )

    def preview(self, item: ActionCenterItem) -> ActionResult:
        if item.manual_only:
            return ActionResult(
                success=True,
                message=f"[PREVIEW] Manual-only action: {item.title}",
                preview=True,
                data={"action_center": item.to_dict()},
                action_id=item.id,
            )
        if not item.command_preview:
            return ActionResult.fail("Action has no command preview.", data={"action_center": item.to_dict()}, action_id=item.id)
        result = self.facade.preview(item.command_preview, privileged=False, action_id=item.id)
        result.data = {**(result.data or {}), "action_center": item.to_dict()}
        return result

    def enqueue(self, items: Iterable[ActionCenterItem]) -> list[ActionCenterItem]:
        queued = [self.queue.enqueue(item) for item in items]
        for item in queued:
            self.history.append({"event": "queued", "action": item.to_dict()})
        return queued

    def execute_next(self, *, confirmed: bool = False, timeout: int = 120) -> ActionResult:
        item = self.queue.next_ready()
        if item is None:
            return ActionResult.fail("No ready action is queued.")
        if item.confirmation_required and not confirmed:
            item.state = "needs_review"
            self.history.append({"event": "blocked-confirmation", "action": item.to_dict()})
            self.queue.finish_current("needs_review", "Confirmation required.")
            return ActionResult.fail("Medium/high-risk action requires explicit confirmation.", data={"action_center": item.to_dict()}, action_id=item.id)
        if not item.command_preview:
            self.queue.finish_current("blocked", "Missing command preview.")
            return ActionResult.fail("Action has no command preview.", data={"action_center": item.to_dict()}, action_id=item.id)

        result = self.facade.execute(item.command_preview, privileged=False, timeout=timeout, action_id=item.id)
        final_state = "succeeded" if result.success else "failed"
        finished = self.queue.finish_current(final_state, result.message)
        if finished:
            self.history.append({"event": "executed", "result": result.to_dict(), "action": finished.to_dict()})
        result.data = {**(result.data or {}), "action_center": finished.to_dict() if finished else item.to_dict()}
        return result

    def recent_history(self, limit: int = 25) -> list[dict[str, object]]:
        return self.history.recent(limit=limit)


def _recommendation_group(kind: str) -> str:
    groups = {
        "failed-service": "services",
        "journal-warning": "journal",
        "dnf-lock": "package-manager",
        "package-health": "package-manager",
        "low-disk": "storage",
        "missing-rollback": "rollback",
    }
    return groups.get(kind, "maintenance")


def _why_this_matters(kind: str) -> str:
    reasons = {
        "failed-service": "A recurring failed service can indicate a startup, dependency, or hardware-related regression.",
        "journal-warning": "Repeated journal warnings make later troubleshooting harder and can point to a recurring system problem.",
        "dnf-lock": "Package manager locks can block updates, installs, and release readiness checks.",
        "package-health": "Package manager health issues can make maintenance and security updates unreliable.",
        "low-disk": "Low root filesystem space can break updates, logs, and desktop sessions.",
        "missing-rollback": "Rollback tooling gives you a safer recovery path before risky maintenance.",
    }
    return reasons.get(kind, "This signal has appeared in the health timeline and should be reviewed.")


def _safe_next_step(kind: str) -> str:
    steps = {
        "failed-service": "Inspect the unit status and logs before restarting or changing service configuration.",
        "journal-warning": "Open the normalized warning details and review recent journal context.",
        "dnf-lock": "Check whether another package operation is active before retrying package commands.",
        "package-health": "Run a read-only repository and package health check before attempting repairs.",
        "low-disk": "Review disk usage and preview cleanup actions before deleting anything.",
        "missing-rollback": "Configure Snapper, Timeshift, or rpm-ostree rollback guidance before risky actions.",
    }
    return steps.get(kind, "Review the snapshot details and choose a previewable follow-up action.")
