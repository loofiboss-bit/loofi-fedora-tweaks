"""Bounded direct-action adapter over Action Center authority."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping

from core.actions.contracts import ActionPlan, ActionRun
from core.actions.eligibility import EligibilityDecision, classify_definition
from core.actions.orchestrator import (
    ActionCenterBusyError,
    ActionCenterError,
    ActionCenterOrchestrator,
    ActionPlanRejectedError,
)
from core.actions.outcomes import OutcomeEvidenceComposer, OutcomeState, OutcomeSummary
from core.fedora_release_policy import FEDORA_RELEASE_POLICY
from core.settings.execution import ExecutionMode, ExecutionSettings, ExecutionSettingsStore

DirectActionStatus = Literal[
    "completed_verified",
    "completed_awaiting_reboot",
    "completed_verification_failed",
    "blocked_by_preflight",
    "review_required",
    "failed",
    "interrupted",
    "cancelled",
    "preview",
]


class DirectActionParameterError(ValueError):
    """Raised when CLI typed parameters are malformed or duplicated."""


@dataclass(frozen=True)
class DirectActionResult:
    """Stable caller-facing result without raw command output."""

    action_id: str
    status: DirectActionStatus
    message: str
    eligibility: EligibilityDecision
    outcome: OutcomeSummary
    plan_id: str = ""
    run_id: str = ""
    correlation_id: str = ""
    preview: tuple[str, ...] = ()
    confirmation_required: bool = False
    settings_notice: str = ""
    dry_run: bool = False
    reboot_policy: str = "none"

    @property
    def display_label(self) -> str:
        return {
            "completed_verified": "Completed and verified",
            "completed_awaiting_reboot": "Completed — reboot required",
            "completed_verification_failed": "Completed, but verification failed",
            "blocked_by_preflight": "Blocked by preflight",
            "review_required": "Review required",
            "failed": "Failed",
            "interrupted": "Interrupted",
            "cancelled": "Cancelled",
            "preview": "Preview only",
        }[self.status]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "loofi.direct-action/v1",
            "schema_version": 1,
            "action_id": self.action_id,
            "status": self.status,
            "label": self.display_label,
            "message": self.message,
            "eligibility": self.eligibility.to_dict(),
            "outcome": self.outcome.to_dict(),
            "plan_id": self.plan_id,
            "run_id": self.run_id,
            "correlation_id": self.correlation_id,
            "preview": list(self.preview),
            "confirmation_required": self.confirmation_required,
            "settings_notice": self.settings_notice,
            "dry_run": self.dry_run,
            "reboot_policy": self.reboot_policy,
        }

    @property
    def exit_code(self) -> int:
        return {
            "completed_verified": 0,
            "completed_awaiting_reboot": 0,
            "preview": 0,
            "review_required": 2,
            "blocked_by_preflight": 3,
            "failed": 1,
            "interrupted": 4,
            "cancelled": 5,
            "completed_verification_failed": 6,
        }[self.status]


def parse_typed_parameters(
    values: list[str],
    schema: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, Any]:
    """Parse only fields declared by the registered Action Center schema."""
    parameters: dict[str, Any] = {}
    declared = schema or {}
    for raw in values:
        if "=" not in raw:
            raise DirectActionParameterError("Each --param must use KEY=VALUE.")
        key, value = raw.split("=", 1)
        key = key.strip()
        if not key or key not in declared:
            raise DirectActionParameterError(f"Parameter is not declared by the action: {key or '<empty>'}.")
        if key in parameters:
            raise DirectActionParameterError(f"Parameter was supplied more than once: {key}.")
        kind = str(declared[key].get("type", "string"))
        if kind in {"integer", "int"}:
            try:
                parameters[key] = int(value)
            except ValueError as exc:
                raise DirectActionParameterError(f"Parameter {key} must be an integer.") from exc
        elif kind in {"boolean", "bool"}:
            normalized = value.strip().lower()
            if normalized not in {"true", "false"}:
                raise DirectActionParameterError(f"Parameter {key} must be true or false.")
            parameters[key] = normalized == "true"
        elif kind in {"object", "array"}:
            import json

            try:
                parsed = json.loads(value)
            except json.JSONDecodeError as exc:
                raise DirectActionParameterError(f"Parameter {key} must be valid JSON.") from exc
            if kind == "object" and not isinstance(parsed, dict):
                raise DirectActionParameterError(f"Parameter {key} must be a JSON object.")
            if kind == "array" and not isinstance(parsed, list):
                raise DirectActionParameterError(f"Parameter {key} must be a JSON array.")
            parameters[key] = parsed
        else:
            parameters[key] = value
    return parameters


class DirectActionService:
    """Run registered actions through the normal Action Center lifecycle."""

    def __init__(
        self,
        *,
        orchestrator: ActionCenterOrchestrator | None = None,
        settings_store: ExecutionSettingsStore | None = None,
        outcome_composer: OutcomeEvidenceComposer | None = None,
    ):
        self.orchestrator = orchestrator or ActionCenterOrchestrator()
        self.settings_store = settings_store or ExecutionSettingsStore()
        self.outcome_composer = outcome_composer or OutcomeEvidenceComposer()

    def eligibility_for(self, action_id: str) -> EligibilityDecision:
        """Return policy classification without probing or mutating the host."""
        definition = self.orchestrator.catalog.get(action_id)
        return classify_definition(definition, action_id=action_id)

    def run(
        self,
        action_id: str,
        parameters: Mapping[str, Any] | None = None,
        *,
        finding_context: Mapping[str, Any] | None = None,
        confirmed: bool = False,
        yes: bool = False,
        dry_run: bool = False,
        execution_mode: ExecutionMode | None = None,
        timeout: int = 120,
        target: str = FEDORA_RELEASE_POLICY.stable_target,
    ) -> DirectActionResult:
        settings = self.settings_store.load()
        eligibility = self.eligibility_for(action_id)
        try:
            if finding_context is not None:
                plan = self.orchestrator.plan_from_finding(
                    check_result_id=str(finding_context.get("check_result_id", "")),
                    finding_fingerprint=str(finding_context.get("finding_fingerprint", "")),
                    origin_route=str(finding_context.get("origin_route", "")),
                    expected_action_id=action_id,
                    target=target,
                )
            else:
                plan = self.orchestrator.plan(action_id, parameters, target=target)
        except (ActionCenterError, OSError, RuntimeError, TypeError, ValueError) as exc:
            return self._error_result(action_id, eligibility, str(exc), settings)

        return self._execute_plan(
            plan,
            eligibility,
            settings=settings,
            confirmed=confirmed,
            yes=yes,
            dry_run=dry_run,
            execution_mode=execution_mode,
            timeout=timeout,
        )

    def run_prepared(
        self,
        plan_id: str,
        *,
        confirmed: bool = False,
        yes: bool = False,
        execution_mode: ExecutionMode | None = None,
        timeout: int = 120,
    ) -> DirectActionResult:
        """Execute one previously prepared plan after a local confirmation.

        GUI callers use this two-step API so the confirmation covers the exact
        preflight preview.  ``prepare_run`` rechecks the digest and host state,
        therefore a changed scope is rejected instead of silently executing a
        different command than the user confirmed.
        """
        settings = self.settings_store.load()
        try:
            plan = self.orchestrator.get_plan(str(plan_id))
        except (ActionCenterError, OSError, RuntimeError, TypeError, ValueError) as exc:
            eligibility = EligibilityDecision("", "blocked", False, "plan_not_found", str(exc))
            return self._error_result("", eligibility, str(exc), settings)
        eligibility = self.eligibility_for(plan.action_id)
        return self._execute_plan(
            plan,
            eligibility,
            settings=settings,
            confirmed=confirmed,
            yes=yes,
            dry_run=False,
            execution_mode=execution_mode,
            timeout=timeout,
        )

    def _execute_plan(
        self,
        plan: ActionPlan,
        eligibility: EligibilityDecision,
        *,
        settings: ExecutionSettings,
        confirmed: bool,
        yes: bool,
        dry_run: bool,
        execution_mode: ExecutionMode | None,
        timeout: int,
    ) -> DirectActionResult:
        preview = tuple(plan.preview)
        if plan.state == "blocked":
            return self._from_plan(
                plan,
                eligibility,
                "blocked_by_preflight",
                plan.policy_decision.explanation,
                settings=settings,
                preview=preview,
            )
        if dry_run:
            return self._from_plan(
                plan,
                eligibility,
                "preview",
                "Dry-run created a plan and did not execute it.",
                settings=settings,
                preview=preview,
                dry_run=True,
            )
        if settings.future_schema and not (confirmed or yes):
            return self._from_plan(
                plan,
                eligibility,
                "review_required",
                "Safety & Execution settings need review before this action can run.",
                settings=settings,
                preview=preview,
                confirmation_required=True,
            )
        if (
            getattr(self.settings_store, "explicit_mode", False)
            and settings.execution_mode == "review_first"
            and not (confirmed or yes)
        ):
            return self._from_plan(
                plan,
                eligibility,
                "review_required",
                "Review-first mode is enabled in Safety & Execution settings; confirm this prepared action locally to continue.",
                settings=settings,
                preview=preview,
                confirmation_required=True,
            )
        if eligibility.review_required or not eligibility.allowed:
            return self._from_plan(
                plan,
                eligibility,
                "review_required",
                eligibility.explanation,
                settings=settings,
                preview=preview,
            )
        effective_mode = execution_mode or settings.effective_mode
        if effective_mode == "review_first":
            return self._from_plan(
                plan,
                eligibility,
                "review_required",
                "Review-first mode is enabled in Safety & Execution settings.",
                settings=settings,
                preview=preview,
            )
        # The compact high-risk confirmation is a GUI interaction policy. Keep
        # the existing CLI/direct-adapter contract review-first unless the
        # caller explicitly opts into the GUI execution mode.
        if eligibility.risk_level == "high" and execution_mode != "direct":
            return self._from_plan(
                plan,
                eligibility,
                "review_required",
                "High-risk actions require the full Action Center review flow outside the GUI.",
                settings=settings,
                preview=preview,
            )
        confirmation_required = eligibility.kind == "confirmation" and (
            settings.confirm_medium_risk or eligibility.risk_level == "high"
        )
        if confirmation_required and not (confirmed or yes):
            return self._from_plan(
                plan,
                eligibility,
                "review_required",
                "One compact confirmation is required before this action can run.",
                settings=settings,
                preview=preview,
                confirmation_required=True,
            )
        if eligibility.kind not in {"direct", "confirmation"} or eligibility.risk_level not in {"low", "medium", "high"}:
            return self._from_plan(
                plan,
                eligibility,
                "review_required",
                "The action is outside direct execution policy.",
                settings=settings,
                preview=preview,
            )
        try:
            run = self.orchestrator.apply(
                plan.plan_id,
                confirmed=True,
                accept_no_rollback=eligibility.risk_level in {"medium", "high"},
                timeout=max(1, min(3600, int(timeout))),
            )
            if settings.automatically_verify and run.state == "verifying":
                run = self.orchestrator.verify(run.run_id)
        except ActionPlanRejectedError as exc:
            current_plan = self.orchestrator.get_plan(plan.plan_id)
            return self._from_plan(
                current_plan,
                eligibility,
                "blocked_by_preflight" if exc.decision.reason_code != "confirmation_required" else "review_required",
                exc.decision.explanation,
                settings=settings,
                preview=tuple(current_plan.preview),
            )
        except ActionCenterBusyError as exc:
            return self._from_plan(plan, eligibility, "interrupted", str(exc), settings=settings, preview=preview)
        except (ActionCenterError, OSError, RuntimeError, TypeError, ValueError) as exc:
            return self._from_plan(plan, eligibility, "failed", str(exc), settings=settings, preview=preview)
        return self._from_run(plan, run, eligibility, settings=settings, preview=preview)

    def _from_plan(
        self,
        plan: ActionPlan,
        eligibility: EligibilityDecision,
        status: DirectActionStatus,
        message: str,
        *,
        settings: ExecutionSettings,
        preview: tuple[str, ...],
        confirmation_required: bool = False,
        dry_run: bool = False,
    ) -> DirectActionResult:
        outcome = self.outcome_composer.compose(plan)
        return DirectActionResult(
            plan.action_id,
            status,
            message,
            eligibility,
            outcome,
            plan_id=plan.plan_id,
            preview=preview,
            confirmation_required=confirmation_required,
            settings_notice=settings.migration_notice,
            dry_run=dry_run,
            reboot_policy=plan.reboot_policy,
        )

    def _from_run(
        self,
        plan: ActionPlan,
        run: ActionRun,
        eligibility: EligibilityDecision,
        *,
        settings: ExecutionSettings,
        preview: tuple[str, ...],
    ) -> DirectActionResult:
        outcome = self.outcome_composer.compose(plan, run)
        status_map: dict[OutcomeState, DirectActionStatus] = {
            "verified": "completed_verified",
            "awaiting_reboot": "completed_awaiting_reboot",
            "verification_failed": "completed_verification_failed",
            "failed": "failed",
            "interrupted": "interrupted",
            "cancelled": "cancelled",
            "partially_verified": "review_required",
            "unverified": "review_required",
            "blocked": "blocked_by_preflight",
        }
        status = status_map[outcome.state]
        return DirectActionResult(
            plan.action_id,
            status,
            outcome.reason,
            eligibility,
            outcome,
            plan_id=plan.plan_id,
            run_id=run.run_id,
            correlation_id=run.correlation_id,
            preview=preview,
            settings_notice=settings.migration_notice,
            reboot_policy=plan.reboot_policy,
        )

    def _error_result(
        self,
        action_id: str,
        eligibility: EligibilityDecision,
        message: str,
        settings: ExecutionSettings,
    ) -> DirectActionResult:
        from core.actions.contracts import ActionPlan, PolicyDecision

        plan = ActionPlan(
            plan_id="",
            action_id=action_id,
            parameters={},
            target=FEDORA_RELEASE_POLICY.stable_target,
            digest="",
            preview=[],
            policy_decision=PolicyDecision(False, "service_error", message),
            risk_level="high",
            privileged=False,
            confirmation_policy="explicit-no-rollback",
            recovery_guidance="Review the Action Center state and retry only after the cause is understood.",
            rollback_supported=False,
            operation_class="manual_only",
            supported_variants=frozenset(),
            affected_resources=(),
        )
        outcome = self.outcome_composer.compose(plan)
        return DirectActionResult(action_id, "failed", message, eligibility, outcome, settings_notice=settings.migration_notice)
