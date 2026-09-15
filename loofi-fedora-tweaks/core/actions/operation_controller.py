"""PyQt-free lifecycle controller for every v29 system operation.

The GUI and CLI deliberately share this controller.  Presentation adapters
may run ``prepare`` and ``confirm`` on the caller thread, hand the returned
``PreparedActionRun`` to a worker, and call ``complete``/``verify`` when that
worker finishes.  The controller owns the policy boundary and durable
Action Center state; no UI object is imported here.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Mapping, Sequence

from core.actions.contracts import ActionPlan, ActionRun, PreparedActionRun
from core.actions.orchestrator import (
    ActionCenterError,
    ActionCenterOrchestrator,
    ActionPlanRejectedError,
)
from core.executor.action_result import ActionResult
from core.fedora_release_policy import FEDORA_RELEASE_POLICY


OperationExecutor = Callable[..., ActionResult]
OperationEventSink = Callable[["OperationEvent"], None]


class OperationControllerError(ActionCenterError):
    """Base error for invalid controller input or lifecycle usage."""


class OperationNotPreparedError(OperationControllerError):
    """Raised when a run is requested without a prepared execution token."""


class OperationConfirmationRequired(OperationControllerError):
    """Optional exception for adapters that prefer exception-based gating."""


@dataclass(frozen=True)
class OperationEvent:
    """One presentation-neutral lifecycle update."""

    phase: str
    status: str
    message: str
    action_id: str = ""
    plan_id: str = ""
    run_id: str = ""
    correlation_id: str = ""
    timestamp: float = field(default_factory=time.time)
    data: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "status": self.status,
            "message": self.message,
            "action_id": self.action_id,
            "plan_id": self.plan_id,
            "run_id": self.run_id,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp,
            "data": dict(self.data),
        }


@dataclass(frozen=True)
class OperationTicket:
    """Prepared, reviewable plan returned before any host mutation."""

    plan: ActionPlan
    prepared: PreparedActionRun | None = None
    phase: str = "prepare"
    events: tuple[OperationEvent, ...] = ()

    @property
    def action_id(self) -> str:
        return self.plan.action_id

    @property
    def plan_id(self) -> str:
        return self.plan.plan_id

    @property
    def confirmation_required(self) -> bool:
        return self.plan.state == "needs_review" or self.plan.risk_level in {"medium", "high"}

    @property
    def blocked(self) -> bool:
        return self.plan.state == "blocked"

    @property
    def preview(self) -> tuple[str, ...]:
        return tuple(self.plan.preview)

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "plan": self.plan.to_dict(),
            "prepared": self.prepared.to_dict() if self.prepared else None,
            "confirmation_required": self.confirmation_required,
            "blocked": self.blocked,
            "events": [event.to_dict() for event in self.events],
        }


@dataclass(frozen=True)
class OperationOutcome:
    """Stable result returned by each lifecycle step.

    ``result`` and ``run`` are retained as typed objects for adapters that
    need richer evidence, while ``to_dict`` provides a bounded JSON view for
    CLI, activity, and support surfaces.
    """

    action_id: str
    status: str
    phase: str
    message: str
    plan_id: str = ""
    run_id: str = ""
    correlation_id: str = ""
    plan: ActionPlan | None = None
    run: ActionRun | None = None
    prepared: PreparedActionRun | None = None
    result: ActionResult | None = None
    recovery_guidance: str = ""
    needs_reboot: bool = False
    confirmation_required: bool = False
    data: Mapping[str, Any] = field(default_factory=dict)
    events: tuple[OperationEvent, ...] = ()

    @property
    def success(self) -> bool:
        return self.status in {"succeeded", "completed_verified", "verified"}

    @property
    def terminal(self) -> bool:
        return self.status in {
            "succeeded",
            "completed_verified",
            "verified",
            "failed",
            "verification_failed",
            "cancelled",
            "interrupted",
            "blocked",
            "skipped",
        }

    @property
    def awaiting_confirmation(self) -> bool:
        return self.status == "confirmation_required" or self.confirmation_required

    @property
    def recovery_required(self) -> bool:
        return self.status in {
            "failed",
            "verification_failed",
            "interrupted",
            "recovery_required",
        }

    def with_event(self, event: OperationEvent) -> "OperationOutcome":
        return replace(self, events=(*self.events, event))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "loofi.operation-outcome/v1",
            "schema_version": 1,
            "action_id": self.action_id,
            "status": self.status,
            "phase": self.phase,
            "message": self.message,
            "plan_id": self.plan_id,
            "run_id": self.run_id,
            "correlation_id": self.correlation_id,
            "plan": self.plan.to_dict() if self.plan else None,
            "run": self.run.to_dict() if self.run else None,
            "prepared": self.prepared.to_dict() if self.prepared else None,
            "result": self.result.to_dict() if self.result else None,
            "recovery_guidance": self.recovery_guidance,
            "needs_reboot": self.needs_reboot,
            "confirmation_required": self.confirmation_required,
            "data": dict(self.data),
            "events": [event.to_dict() for event in self.events],
        }


def _state_status(state: str) -> tuple[str, str]:
    """Map durable ActionRun state to controller phase and public status."""
    if state == "verifying":
        return "verify", "verifying"
    if state == "awaiting_reboot":
        return "verify", "awaiting_reboot"
    if state == "succeeded":
        return "verify", "succeeded"
    if state == "verification_failed":
        return "recovery", "verification_failed"
    if state in {"failed", "cancelled", "interrupted"}:
        return "recovery", state
    if state == "running":
        return "run", "running"
    return "recovery", state or "failed"


class OperationController:
    """Single PyQt-free prepare/confirm/run/verify/recovery boundary."""

    def __init__(
        self,
        *,
        orchestrator: ActionCenterOrchestrator | None = None,
        facade: Any | None = None,
        clock: Callable[[], float] = time.time,
        event_sink: OperationEventSink | None = None,
        progress_sink: OperationEventSink | None = None,
    ):
        # Supplying a facade without an orchestrator is useful for callers
        # that only want the default catalog, while an injected orchestrator
        # remains authoritative when tests or a host adapter provide one.
        self.orchestrator = orchestrator or ActionCenterOrchestrator(facade=facade)
        self.facade = facade or getattr(self.orchestrator, "facade", None)
        self.clock = clock
        self.event_sink = event_sink or progress_sink
        self.last_event: OperationEvent | None = None

    def _event(
        self,
        phase: str,
        status: str,
        message: str,
        *,
        action_id: str = "",
        plan_id: str = "",
        run_id: str = "",
        correlation_id: str = "",
        data: Mapping[str, Any] | None = None,
    ) -> OperationEvent:
        event = OperationEvent(
            phase=phase,
            status=status,
            message=message,
            action_id=action_id,
            plan_id=plan_id,
            run_id=run_id,
            correlation_id=correlation_id,
            timestamp=self.clock(),
            data=dict(data or {}),
        )
        self.last_event = event
        if self.event_sink is not None:
            try:
                self.event_sink(event)
            except (AttributeError, RuntimeError, TypeError, ValueError):
                # Progress sinks are presentation concerns and must never
                # change the trusted operation outcome.
                pass
        return event

    @staticmethod
    def _plan_for(value: OperationTicket | ActionPlan | OperationOutcome | str) -> ActionPlan:
        if isinstance(value, OperationTicket):
            return value.plan
        if isinstance(value, OperationOutcome) and value.plan is not None:
            return value.plan
        if isinstance(value, ActionPlan):
            return value
        raise OperationControllerError("An ActionPlan, OperationTicket, or plan ID is required.")

    def _load_plan(self, value: OperationTicket | ActionPlan | OperationOutcome | str) -> ActionPlan:
        if isinstance(value, str):
            return self.orchestrator.get_plan(value)
        return self._plan_for(value)

    def prepare(
        self,
        action_id: str,
        parameters: Mapping[str, Any] | None = None,
        *,
        target: str = FEDORA_RELEASE_POLICY.stable_target,
    ) -> OperationTicket:
        """Create and persist a fresh plan without executing anything."""
        plan = self.orchestrator.plan(action_id, parameters, target=target)
        status = "blocked" if plan.state == "blocked" else "prepared"
        event = self._event(
            "prepare",
            status,
            plan.policy_decision.explanation,
            action_id=plan.action_id,
            plan_id=plan.plan_id,
            data={"reason_code": plan.policy_decision.reason_code},
        )
        return OperationTicket(plan=plan, events=(event,))

    # Explicit alias used by adapters that prefer the word operation.
    prepare_operation = prepare

    def confirm(
        self,
        ticket: OperationTicket | ActionPlan | OperationOutcome | str,
        *,
        confirmed: bool = False,
        accept_no_rollback: bool = False,
    ) -> OperationOutcome:
        """Revalidate a plan and acquire an ephemeral execution token."""
        plan = self._load_plan(ticket)
        if plan.state == "blocked":
            event = self._event(
                "confirm",
                "blocked",
                plan.policy_decision.explanation,
                action_id=plan.action_id,
                plan_id=plan.plan_id,
                data={"reason_code": plan.policy_decision.reason_code},
            )
            return OperationOutcome(
                action_id=plan.action_id,
                status="blocked",
                phase="confirm",
                message=plan.policy_decision.explanation,
                plan_id=plan.plan_id,
                plan=plan,
                recovery_guidance=plan.recovery_guidance,
                data={"reason_code": plan.policy_decision.reason_code},
                events=(event,),
            )
        try:
            prepared = self.orchestrator.prepare_run(
                plan.plan_id,
                confirmed=confirmed,
                accept_no_rollback=accept_no_rollback,
            )
        except ActionPlanRejectedError as exc:
            current_plan = plan
            try:
                current_plan = self.orchestrator.get_plan(plan.plan_id)
            except (ActionCenterError, OSError, RuntimeError, TypeError, ValueError):
                pass
            requires_confirmation = exc.decision.reason_code in {
                "confirmation_required",
                "no_rollback_acceptance_required",
            }
            status = "confirmation_required" if requires_confirmation else "blocked"
            event = self._event(
                "confirm",
                status,
                exc.decision.explanation,
                action_id=plan.action_id,
                plan_id=plan.plan_id,
                data={"reason_code": exc.decision.reason_code},
            )
            return OperationOutcome(
                action_id=plan.action_id,
                status=status,
                phase="confirm",
                message=exc.decision.explanation,
                plan_id=plan.plan_id,
                plan=current_plan,
                recovery_guidance=current_plan.recovery_guidance,
                confirmation_required=requires_confirmation,
                data={"reason_code": exc.decision.reason_code, "alternative": exc.decision.alternative},
                events=(event,),
            )
        except (ActionCenterError, OSError, RuntimeError, TypeError, ValueError) as exc:
            event = self._event(
                "confirm",
                "blocked",
                str(exc),
                action_id=plan.action_id,
                plan_id=plan.plan_id,
            )
            return OperationOutcome(
                action_id=plan.action_id,
                status="blocked",
                phase="confirm",
                message=str(exc),
                plan_id=plan.plan_id,
                plan=plan,
                recovery_guidance=plan.recovery_guidance,
                events=(event,),
            )
        event = self._event(
            "confirm",
            "prepared",
            "Action is confirmed and ready to run.",
            action_id=prepared.action_id,
            plan_id=prepared.plan_id,
            run_id=prepared.run_id,
            correlation_id=prepared.correlation_id,
        )
        prior_events = ticket.events if isinstance(ticket, OperationTicket) else ()
        return OperationOutcome(
            action_id=prepared.action_id,
            status="prepared",
            phase="run",
            message="Action is confirmed and ready to run.",
            plan_id=prepared.plan_id,
            run_id=prepared.run_id,
            correlation_id=prepared.correlation_id,
            plan=plan,
            prepared=prepared,
            recovery_guidance=plan.recovery_guidance,
            events=(*prior_events, event),
        )

    # Alias matching the lower-level orchestrator vocabulary.
    authorize = confirm

    @staticmethod
    def _prepared_for(value: OperationOutcome | OperationTicket | PreparedActionRun) -> PreparedActionRun:
        if isinstance(value, PreparedActionRun):
            return value
        if isinstance(value, OperationOutcome) and value.prepared is not None:
            return value.prepared
        if isinstance(value, OperationTicket) and value.prepared is not None:
            return value.prepared
        raise OperationNotPreparedError("Confirm the operation before requesting a run.")

    def run(
        self,
        prepared: OperationOutcome | OperationTicket | PreparedActionRun,
        *,
        timeout: int = 120,
        executor: OperationExecutor | None = None,
    ) -> OperationOutcome:
        """Execute one prepared vector through the Action Center authority."""
        token = self._prepared_for(prepared)
        prior_events = prepared.events if isinstance(prepared, OperationOutcome) else (
            prepared.events if isinstance(prepared, OperationTicket) else ()
        )
        plan = self.orchestrator.get_plan(token.plan_id)
        event = self._event(
            "run",
            "running",
            "Action is running.",
            action_id=token.action_id,
            plan_id=token.plan_id,
            run_id=token.run_id,
            correlation_id=token.correlation_id,
        )
        runner = executor
        try:
            if runner is None:
                if self.facade is None:
                    raise OperationControllerError("No command facade is configured for operation execution.")
                result = self.facade.execute(
                    token.command,
                    privileged=token.privileged,
                    timeout=max(1, int(timeout)),
                    action_id=token.action_id,
                    authority="action_center",
                )
            else:
                result = runner(
                    token.command,
                    privileged=token.privileged,
                    timeout=max(1, int(timeout)),
                    action_id=token.action_id,
                    authority="action_center",
                )
            if not isinstance(result, ActionResult):
                result = ActionResult.fail(
                    "Operation executor returned an invalid result.",
                    exit_code=-1,
                    action_id=token.action_id,
                )
        except (ActionCenterError, OSError, RuntimeError, TypeError, ValueError) as exc:
            result = ActionResult.fail(
                f"Execution boundary failed: {exc}",
                exit_code=-1,
                action_id=token.action_id,
            )
        try:
            run = self.orchestrator.complete_run(token.run_id, result)
        except (ActionCenterError, OSError, RuntimeError, TypeError, ValueError) as exc:
            return OperationOutcome(
                action_id=token.action_id,
                status="failed",
                phase="recovery",
                message=str(exc),
                plan_id=token.plan_id,
                run_id=token.run_id,
                correlation_id=token.correlation_id,
                plan=plan,
                prepared=token,
                result=result,
                recovery_guidance=plan.recovery_guidance,
                data={"execution_result": result.to_dict()},
                events=(*prior_events, event),
            )
        return self._outcome_from_run(
            run,
            plan=plan,
            prepared=token,
            result=result,
            prior_events=(*prior_events, event),
        )

    def complete(
        self,
        prepared: OperationOutcome | OperationTicket | PreparedActionRun,
        result: ActionResult,
    ) -> OperationOutcome:
        """Complete a worker-executed token without running it in this thread."""
        token = self._prepared_for(prepared)
        prior_events = prepared.events if isinstance(prepared, OperationOutcome) else (
            prepared.events if isinstance(prepared, OperationTicket) else ()
        )
        try:
            plan = self.orchestrator.get_plan(token.plan_id)
            run = self.orchestrator.complete_run(token.run_id, result)
        except (ActionCenterError, OSError, RuntimeError, TypeError, ValueError) as exc:
            event = self._event(
                "recovery",
                "failed",
                str(exc),
                action_id=token.action_id,
                plan_id=token.plan_id,
                run_id=token.run_id,
                correlation_id=token.correlation_id,
            )
            return OperationOutcome(
                action_id=token.action_id,
                status="failed",
                phase="recovery",
                message=str(exc),
                plan_id=token.plan_id,
                run_id=token.run_id,
                correlation_id=token.correlation_id,
                prepared=token,
                result=result,
                data={"execution_result": result.to_dict()},
                events=(*prior_events, event),
            )
        event = self._event(
            "run",
            run.state,
            result.message,
            action_id=token.action_id,
            plan_id=token.plan_id,
            run_id=token.run_id,
            correlation_id=token.correlation_id,
        )
        return self._outcome_from_run(
            run,
            plan=plan,
            prepared=token,
            result=result,
            prior_events=(*prior_events, event),
        )

    complete_run = complete

    def verify(self, value: OperationOutcome | ActionRun | str) -> OperationOutcome:
        """Verify a completed execution, including reboot hand-off."""
        if isinstance(value, OperationOutcome):
            run_id = value.run_id
            prior_events = value.events
        elif isinstance(value, ActionRun):
            run_id = value.run_id
            prior_events = ()
        else:
            run_id = str(value)
            prior_events = ()
        if not run_id:
            raise OperationControllerError("A run ID is required for verification.")
        run = self.orchestrator.get_run(run_id)
        plan = self.orchestrator.get_plan(run.plan_id)
        event = self._event(
            "verify",
            "verifying",
            "Operation verification is running.",
            action_id=run.action_id,
            plan_id=run.plan_id,
            run_id=run.run_id,
            correlation_id=run.correlation_id,
        )
        try:
            verified = self.orchestrator.verify(run.run_id)
        except (ActionCenterError, OSError, RuntimeError, TypeError, ValueError) as exc:
            return OperationOutcome(
                action_id=run.action_id,
                status="verification_failed",
                phase="recovery",
                message=str(exc),
                plan_id=run.plan_id,
                run_id=run.run_id,
                correlation_id=run.correlation_id,
                plan=plan,
                run=run,
                recovery_guidance=plan.recovery_guidance,
                events=(*prior_events, event),
            )
        return self._outcome_from_run(
            verified,
            plan=plan,
            prior_events=(*prior_events, event),
        )

    verify_run = verify

    def recover(
        self,
        value: OperationOutcome | ActionRun | str,
        *,
        reason: str = "manual-recovery-requested",
    ) -> OperationOutcome:
        """Expose recovery guidance and interrupt active work safely.

        Recovery is deliberately guidance-only.  This method never retries,
        rolls back, or reboots the host automatically.
        """
        if isinstance(value, OperationOutcome):
            run_id = value.run_id
            prior_events = value.events
        elif isinstance(value, ActionRun):
            run_id = value.run_id
            prior_events = ()
        else:
            run_id = str(value)
            prior_events = ()
        if not run_id:
            raise OperationControllerError("A run ID is required for recovery guidance.")
        run = self.orchestrator.get_run(run_id)
        plan = self.orchestrator.get_plan(run.plan_id)
        if run.state in {"running", "verifying"}:
            run = self.orchestrator.interrupt_run(run.run_id, reason)
        event = self._event(
            "recovery",
            "recovery_required",
            plan.recovery_guidance or "Review the operation result manually before continuing.",
            action_id=run.action_id,
            plan_id=run.plan_id,
            run_id=run.run_id,
            correlation_id=run.correlation_id,
            data={"automatic_action": "none", "reason": reason},
        )
        return OperationOutcome(
            action_id=run.action_id,
            status="recovery_required",
            phase="recovery",
            message=plan.recovery_guidance or "Manual recovery review is required.",
            plan_id=run.plan_id,
            run_id=run.run_id,
            correlation_id=run.correlation_id,
            plan=plan,
            run=run,
            recovery_guidance=plan.recovery_guidance,
            data={"automatic_action": "none", "reason": reason},
            events=(*prior_events, event),
        )

    recovery = recover

    def execute(
        self,
        action_id: str,
        parameters: Mapping[str, Any] | None = None,
        *,
        confirmed: bool = False,
        accept_no_rollback: bool = False,
        timeout: int = 120,
        target: str = FEDORA_RELEASE_POLICY.stable_target,
        executor: OperationExecutor | None = None,
        auto_verify: bool = True,
    ) -> OperationOutcome:
        """Run the complete golden path for one action.

        ``auto_verify`` may be disabled by an asynchronous presentation
        adapter; the returned outcome then remains in ``verifying`` and can be
        passed to :meth:`verify` later.
        """
        try:
            ticket = self.prepare(action_id, parameters, target=target)
        except (ActionCenterError, OSError, RuntimeError, TypeError, ValueError) as exc:
            return OperationOutcome(
                action_id=str(action_id),
                status="blocked",
                phase="prepare",
                message=str(exc),
                data={"reason_code": "prepare_failed"},
            )
        if ticket.blocked:
            return OperationOutcome(
                action_id=ticket.action_id,
                status="blocked",
                phase="prepare",
                message=ticket.plan.policy_decision.explanation,
                plan_id=ticket.plan_id,
                plan=ticket.plan,
                recovery_guidance=ticket.plan.recovery_guidance,
                data={"reason_code": ticket.plan.policy_decision.reason_code},
            )
        confirmed_outcome = self.confirm(
            ticket,
            confirmed=confirmed,
            accept_no_rollback=accept_no_rollback,
        )
        if confirmed_outcome.status != "prepared":
            return confirmed_outcome
        running = self.run(confirmed_outcome, timeout=timeout, executor=executor)
        if auto_verify and running.status == "verifying":
            return self.verify(running)
        return running

    run_action = execute

    def execute_bundle(
        self,
        bundle: Any,
        *,
        confirmed: bool = False,
        accept_no_rollback: bool = False,
        timeout: int = 120,
        item_executor: Callable[[Any], OperationOutcome | ActionResult] | None = None,
        target: str = FEDORA_RELEASE_POLICY.stable_target,
    ) -> Any:
        """Execute a versioned application or Tune bundle with its policy.

        ``item_executor`` is a deterministic test/adapter seam.  It receives
        an :class:`ActionBundleItem` and must return an ``OperationOutcome`` or
        ``ActionResult``; the default uses this controller's golden path.
        """
        from core.actions.bundles import BundleExecutionPolicy, BundleItemResult, BundleKind, BundleOutcome

        try:
            catalog = getattr(self.orchestrator, "catalog", None)
            known_action_ids = (
                {definition.id for definition in catalog.list()}
                if catalog is not None and callable(getattr(catalog, "list", None))
                else None
            )
            bundle.assert_valid(known_action_ids=known_action_ids)
        except (AttributeError, ValueError, TypeError) as exc:
            kind: BundleKind = (
                "tune_profile"
                if str(getattr(bundle, "kind", "")) == "tune_profile"
                else "application_install"
            )
            execution_policy: BundleExecutionPolicy = (
                "stop_on_error" if kind == "tune_profile" else "continue_on_error"
            )
            return BundleOutcome(
                bundle_id=str(getattr(bundle, "bundle_id", "")),
                kind=kind,
                execution_policy=execution_policy,
                status="blocked",
                message=str(exc),
            )
        results: list[BundleItemResult] = []
        stopped = False
        for item in bundle.items:
            if stopped:
                results.append(
                    BundleItemResult(
                        item_id=item.item_id,
                        action_id=item.action_id,
                        status="skipped",
                        message="Skipped because an earlier ordered operation failed.",
                        skipped=True,
                    )
                )
                continue
            try:
                raw = (
                    item_executor(item)
                    if item_executor is not None
                    else self.execute(
                        item.action_id,
                        item.parameters,
                        confirmed=confirmed,
                        accept_no_rollback=accept_no_rollback,
                        timeout=timeout,
                        target=target,
                    )
                )
                outcome = self._outcome_from_raw(raw, action_id=item.action_id)
            except (ActionCenterError, OSError, RuntimeError, TypeError, ValueError) as exc:
                outcome = OperationOutcome(
                    action_id=item.action_id,
                    status="failed",
                    phase="recovery",
                    message=str(exc),
                )
            results.append(
                BundleItemResult(
                    item_id=item.item_id,
                    action_id=item.action_id,
                    status=outcome.status,
                    message=outcome.message,
                    plan_id=outcome.plan_id,
                    run_id=outcome.run_id,
                    correlation_id=outcome.correlation_id,
                    data=dict(outcome.data),
                )
            )
            if bundle.stop_on_error and not outcome.success:
                stopped = True
        successes = sum(item.success for item in results)
        failures = [item for item in results if not item.success and not item.skipped]
        skipped = sum(item.skipped for item in results)
        if failures:
            status = "partial_failure" if successes else "failed"
            message = f"{successes}/{len(bundle.items)} bundle operations completed and verified."
        elif skipped:
            status = "partial_failure"
            message = f"{successes}/{len(bundle.items)} bundle operations completed; {skipped} skipped."
        else:
            status = "succeeded"
            message = f"{successes}/{len(bundle.items)} bundle operations completed and verified."
        recovery = next((item.message for item in failures if item.message), "")
        return BundleOutcome(
            bundle_id=bundle.bundle_id,
            kind=bundle.kind,
            execution_policy=bundle.execution_policy,
            status=status,
            message=message,
            items=tuple(results),
            digest=bundle.digest,
            recovery_guidance=recovery,
        )

    run_bundle = execute_bundle

    @staticmethod
    def _outcome_from_raw(raw: OperationOutcome | ActionResult, *, action_id: str) -> OperationOutcome:
        if isinstance(raw, OperationOutcome):
            return raw
        if isinstance(raw, ActionResult):
            return OperationOutcome(
                action_id=action_id,
                status="succeeded" if raw.success else "failed",
                phase="verify" if raw.success else "recovery",
                message=raw.message,
                result=raw,
                needs_reboot=raw.needs_reboot,
                data=dict(raw.data or {}),
            )
        raise OperationControllerError("Bundle item executor returned an invalid result.")

    def _outcome_from_run(
        self,
        run: ActionRun,
        *,
        plan: ActionPlan,
        prepared: PreparedActionRun | None = None,
        result: ActionResult | None = None,
        prior_events: Sequence[OperationEvent] = (),
    ) -> OperationOutcome:
        phase, status = _state_status(run.state)
        event = self._event(
            phase,
            status,
            (result.message if result is not None else "Operation state updated."),
            action_id=run.action_id,
            plan_id=run.plan_id,
            run_id=run.run_id,
            correlation_id=run.correlation_id,
            data={"run_state": run.state},
        )
        data: dict[str, Any] = {}
        if run.execution_result:
            data["execution_result"] = dict(run.execution_result)
        if run.verification_result:
            data["verification_result"] = dict(run.verification_result)
        return OperationOutcome(
            action_id=run.action_id,
            status=status,
            phase=phase,
            message=(result.message if result is not None else "Operation state updated."),
            plan_id=run.plan_id,
            run_id=run.run_id,
            correlation_id=run.correlation_id,
            plan=plan,
            run=run,
            prepared=prepared,
            result=result,
            recovery_guidance=plan.recovery_guidance,
            needs_reboot=run.state == "awaiting_reboot" or run.reboot_required,
            data=data,
            events=(*prior_events, event),
        )


# Compatibility aliases for integrations that choose a more domain-specific
# name.  They all point to the same implementation and state machine.
ActionOperationController = OperationController
OperationResult = OperationOutcome
PreparedOperation = OperationTicket


__all__ = [
    "ActionOperationController",
    "OperationConfirmationRequired",
    "OperationController",
    "OperationControllerError",
    "OperationEvent",
    "OperationEventSink",
    "OperationExecutor",
    "OperationNotPreparedError",
    "OperationOutcome",
    "OperationResult",
    "OperationTicket",
    "PreparedOperation",
]
