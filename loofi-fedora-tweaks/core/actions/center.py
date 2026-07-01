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

    def candidates_from_readiness(self, target: str = "44") -> list[ActionCenterItem]:
        plan = ReadinessActionService.build_plan(target)
        return [self.from_readiness_candidate(candidate, target=target) for candidate in plan.candidates]

    def from_readiness_candidate(self, candidate: ReadinessActionCandidate, *, target: str = "44") -> ActionCenterItem:
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
            metadata={"related_check_id": candidate.related_check_id},
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
