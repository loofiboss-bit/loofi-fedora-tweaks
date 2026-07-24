"""Policy-backed v14 Action Center planning, execution, and verification."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from core.actions.catalog import ActionCatalog, SystemActionRuntime, validate_parameters
from core.actions.contracts import ActionDefinition, ActionPlan, ActionRun, ActionRuntime, FindingContext, PolicyDecision, PreparedActionRun, VerificationDecision
from core.actions.stores import ActionPlanStore, ActionRunStore
from core.executor.action_result import ActionResult
from core.executor.command_facade import CommandFacade
from core.executor.command_policy import CommandValidationError, validate_command_vector
from core.fedora_release_policy import FEDORA_RELEASE_POLICY, FedoraReleasePolicy
from core.state.atomic_io import StateBusyError, advisory_lock
from core.state.paths import StatePaths
from services.system.system import SystemManager

PLAN_TTL_SECONDS = 30 * 60


class ActionCenterError(RuntimeError):
    """Base error for v14 Action Center orchestration."""


class ActionPlanNotFoundError(ActionCenterError):
    pass


class ActionRunNotFoundError(ActionCenterError):
    pass


class ActionCenterBusyError(ActionCenterError):
    pass


class ActionPlanRejectedError(ActionCenterError):
    """Carries the machine-readable decision which rejected a plan."""

    def __init__(self, decision: PolicyDecision):
        super().__init__(decision.explanation)
        self.decision = decision


class ActionPlanIntegrityError(ActionCenterError):
    pass


class ActionCenterOrchestrator:
    """Regenerate commands from definitions and persist every lifecycle boundary."""

    def __init__(
        self,
        *,
        facade: CommandFacade | None = None,
        catalog: ActionCatalog | None = None,
        plan_store: ActionPlanStore | None = None,
        run_store: ActionRunStore | None = None,
        lease_path: Path | None = None,
        runtime: ActionRuntime | None = None,
        system_manager: type[SystemManager] = SystemManager,
        clock: Callable[[], float] = time.time,
        id_factory: Callable[[], str] | None = None,
        recover_interrupted: bool = True,
        release_policy: FedoraReleasePolicy = FEDORA_RELEASE_POLICY,
        finding_handoff: Any | None = None,
    ):
        self.facade = facade or CommandFacade()
        self.catalog = catalog or ActionCatalog()
        self.plan_store = plan_store or ActionPlanStore()
        self.run_store = run_store or ActionRunStore()
        self.lease_path = lease_path or (StatePaths.from_environment().runtime / "action_center_mutation")
        self.runtime = runtime or SystemActionRuntime(self.facade, system_manager)
        self.clock = clock
        self.id_factory = id_factory or (lambda: str(uuid.uuid4()))
        self.release_policy = release_policy
        self.finding_handoff = finding_handoff
        self._held_leases: dict[str, AbstractContextManager[None]] = {}
        if recover_interrupted:
            self._recover_interrupted_if_unleased()

    def plan(
        self,
        action_id: str,
        parameters: Mapping[str, Any] | None = None,
        *,
        target: str = FEDORA_RELEASE_POLICY.stable_target,
    ) -> ActionPlan:
        """Create an ordinary v18-compatible plan without finding context."""
        return self._create_plan(
            action_id,
            parameters,
            target=target,
            finding_context=None,
        )

    def plan_from_finding(
        self,
        *,
        check_result_id: str,
        finding_fingerprint: str,
        origin_route: str,
        expected_action_id: str,
        target: str = FEDORA_RELEASE_POLICY.stable_target,
    ) -> ActionPlan:
        """Re-resolve persisted evidence before creating one reviewed plan."""
        if self.finding_handoff is None:
            from core.system_check.handoff import FindingActionHandoff

            self.finding_handoff = FindingActionHandoff(catalog=self.catalog)
        review = self.finding_handoff.resolve(
            check_result_id=check_result_id,
            finding_fingerprint=finding_fingerprint,
            origin_route=origin_route,
        )
        if review.action_id != str(expected_action_id):
            from core.system_check.handoff import FindingHandoffError

            raise FindingHandoffError(
                "finding_action_mismatch",
                "The requested action does not match the saved finding.",
            )
        return self._create_plan(
            review.action_id,
            review.parameters_dict(),
            target=target,
            finding_context=review.context,
        )

    def _create_plan(
        self,
        action_id: str,
        parameters: Mapping[str, Any] | None,
        *,
        target: str,
        finding_context: FindingContext | None,
    ) -> ActionPlan:
        """Create a 30-minute plan after schema validation and fresh preflight."""
        now = self.clock()
        normalized = dict(parameters or {})
        definition = self.catalog.get(action_id)
        if definition is None:
            decision = self.catalog.denied(action_id)
            plan = ActionPlan(
                plan_id=self.id_factory(),
                action_id=action_id,
                parameters=normalized,
                target=target,
                digest="",
                preview=[],
                policy_decision=decision,
                risk_level="high",
                privileged=False,
                confirmation_policy="explicit-no-rollback",
                recovery_guidance=decision.alternative,
                rollback_supported=False,
                operation_class="manual_only",
                supported_variants=frozenset(),
                reboot_policy="none",
                affected_resources=(),
                finding_context=finding_context,
                created_at=now,
                expires_at=now + PLAN_TTL_SECONDS,
            )
            plan.digest = self._digest(
                plan.action_id,
                plan.parameters,
                target,
                plan.preview,
                decision,
                self._plan_definition_fields(plan),
                finding_context,
            )
            plan.transition("blocked", decision.reason_code, at=now)
            self.plan_store.save(plan)
            return plan

        parameters_decision = validate_parameters(definition, normalized)
        preview: list[str] = []
        if parameters_decision.allowed:
            try:
                if definition.operation_class == "manual_only":
                    decision = definition.preflight_checker(normalized, self.runtime)
                else:
                    preview = self._render(definition, normalized)
                    decision = definition.preflight_checker(normalized, self.runtime)
                    if decision.allowed:
                        decision = self._variant_decision(definition) or decision
                if self.release_policy.is_preview_target(target):
                    decision = PolicyDecision(
                        False,
                        "preview_target_read_only",
                        f"Fedora {self.release_policy.preview_release} remains a read-only preview target.",
                        f"Review preview diagnostics and create a Fedora {self.release_policy.stable_release} plan for an audited action.",
                        {"target": target},
                    )
                elif not self.release_policy.is_stable_target(target):
                    decision = PolicyDecision(
                        False,
                        "unsupported_target",
                        f"Unsupported action target: {target}.",
                        f"Use the Fedora {self.release_policy.stable_release} stable target.",
                        {"target": target},
                    )
                else:
                    host_decision = self._host_target_decision(target)
                    decision = host_decision or decision
            except (CommandValidationError, ValueError) as exc:
                decision = PolicyDecision(False, "command_policy_rejected", str(exc))
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                decision = PolicyDecision(False, "preflight_failed", f"Action preflight failed safely: {exc}")
        else:
            decision = parameters_decision
        plan = ActionPlan(
            plan_id=self.id_factory(),
            action_id=action_id,
            parameters=normalized,
            target=target,
            digest="",
            preview=preview,
            policy_decision=decision,
            risk_level=definition.risk_level,
            privileged=self._is_privileged(definition, normalized),
            confirmation_policy=definition.confirmation_policy,
            recovery_guidance=definition.recovery_guidance,
            rollback_supported=definition.rollback_supported,
            operation_class=definition.operation_class,
            supported_variants=definition.supported_variants,
            reboot_policy=definition.reboot_policy,
            affected_resources=definition.affected_resources,
            finding_context=finding_context,
            created_at=now,
            expires_at=now + PLAN_TTL_SECONDS,
        )
        plan.digest = self._digest(
            action_id,
            normalized,
            target,
            preview,
            decision,
            self._definition_fields(definition, normalized),
            finding_context,
        )
        if not decision.allowed:
            state = "blocked"
        elif definition.risk_level in {"medium", "high"}:
            state = "needs_review"
        else:
            state = "ready"
        plan.transition(state, decision.reason_code, at=now)  # type: ignore[arg-type]
        self.plan_store.save(plan)
        return plan

    def get_plan(self, plan_id: str) -> ActionPlan:
        plan = self.plan_store.get(plan_id)
        if plan is None:
            raise ActionPlanNotFoundError(f"Action plan not found: {plan_id}")
        return plan

    def get_run(self, run_id: str) -> ActionRun:
        run = self.run_store.get(run_id)
        if run is None:
            raise ActionRunNotFoundError(f"Action run not found: {run_id}")
        return run

    def preview(self, plan_id: str) -> ActionResult:
        """Regenerate a preview; never execute the vector stored in the plan."""
        plan = self.get_plan(plan_id)
        definition = self._definition_for(plan.action_id)
        self._assert_integrity(plan)
        command = self._render(definition, plan.parameters)
        result = self.facade.preview(command, privileged=plan.privileged, action_id=definition.id)
        result.data = {
            **(result.data or {}),
            "schema_version": 3,
            "plan": plan.to_dict(),
            "policy_decision": plan.policy_decision.to_dict(),
        }
        return result

    def prepare_run(
        self,
        plan_id: str,
        *,
        confirmed: bool,
        accept_no_rollback: bool = False,
    ) -> PreparedActionRun:
        """Revalidate and hold the cross-process lease for async execution."""
        lease = self._acquire_lease()
        run_id = ""
        try:
            plan = self.get_plan(plan_id)
            definition = self._definition_for(plan.action_id)
            now = self.clock()
            if plan.state == "blocked":
                raise ActionPlanRejectedError(plan.policy_decision)
            if plan.is_expired(now):
                decision = PolicyDecision(False, "plan_expired", "The 30-minute action plan has expired.", "Create and review a new plan.")
                self._block_plan(plan, decision, now=now)
                raise ActionPlanRejectedError(decision)
            self._assert_integrity(plan)
            parameter_decision = validate_parameters(definition, plan.parameters)
            if not parameter_decision.allowed:
                self._block_plan(plan, parameter_decision, now=now)
                raise ActionPlanRejectedError(parameter_decision)
            try:
                command = self._render(definition, plan.parameters)
                host_decision = self._host_target_decision(plan.target)
                current_decision = host_decision or definition.preflight_checker(plan.parameters, self.runtime)
                if current_decision.allowed:
                    current_decision = self._variant_decision(definition) or current_decision
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                decision = PolicyDecision(False, "preflight_failed", f"Action preflight failed safely: {exc}")
                self._block_plan(plan, decision, now=now)
                raise ActionPlanRejectedError(decision) from exc
            current_digest = self._digest(
                plan.action_id,
                plan.parameters,
                plan.target,
                command,
                current_decision,
                self._definition_fields(definition, plan.parameters),
                plan.finding_context,
            )
            if current_digest != plan.digest:
                decision = PolicyDecision(
                    False,
                    "system_drift",
                    "System or policy facts changed after preview.",
                    "Create and review a fresh plan.",
                    {"previous_reason": plan.policy_decision.reason_code, "current_reason": current_decision.reason_code},
                )
                self._block_plan(plan, decision, now=now)
                raise ActionPlanRejectedError(decision)
            if not current_decision.allowed:
                self._block_plan(plan, current_decision, now=now)
                raise ActionPlanRejectedError(current_decision)
            if not confirmed:
                raise ActionPlanRejectedError(
                    PolicyDecision(False, "confirmation_required", "Apply requires explicit confirmation.", "Review the exact command and confirm it explicitly.")
                )
            if definition.risk_level in {"medium", "high"} and not definition.rollback_supported and not accept_no_rollback:
                raise ActionPlanRejectedError(
                    PolicyDecision(
                        False,
                        "no_rollback_acceptance_required",
                        "This medium/high-risk action has no supported rollback.",
                        "Explicitly accept the lack of rollback after reviewing recovery guidance.",
                    )
                )
            if plan.state == "needs_review":
                plan.transition("ready", "explicitly-confirmed", at=now)
                self.plan_store.save(plan)
            run_id = self.id_factory()
            correlation_id = self.id_factory()
            run = ActionRun(
                run_id=run_id,
                plan_id=plan.plan_id,
                action_id=plan.action_id,
                correlation_id=correlation_id,
                parameters=dict(plan.parameters),
                operation_class=plan.operation_class,
                supported_variants=plan.supported_variants,
                reboot_policy=plan.reboot_policy,
                affected_resources=plan.affected_resources,
                finding_context=plan.finding_context,
                state="running",
                created_at=now,
                updated_at=now,
                started_at=now,
                recovery_status="available" if definition.rollback_supported else "manual-guidance-only",
                execution_boot_id=self._boot_id(),
                state_history=[{"state": "running", "reason": "execution-started", "timestamp": now}],
            )
            self.run_store.save(run)
            self._held_leases[run_id] = lease
            return PreparedActionRun(
                run_id=run_id,
                plan_id=plan.plan_id,
                action_id=plan.action_id,
                correlation_id=correlation_id,
                command=tuple(command),
                privileged=plan.privileged,
            )
        finally:
            if not run_id or run_id not in self._held_leases:
                lease.__exit__(None, None, None)

    def complete_run(self, run_id: str, result: ActionResult) -> ActionRun:
        """Persist an externally executed result and release its held lease."""
        lease = self._held_leases.get(run_id)
        if lease is None:
            raise ActionCenterError("Run completion requires the orchestrator that prepared the held lease.")
        try:
            run = self.get_run(run_id)
            if run.state != "running":
                raise ActionCenterError(f"Run is not awaiting execution completion: {run.state}")
            run.execution_result = result.to_dict()
            now = self.clock()
            if result.success:
                run.transition("verifying", "execution-succeeded", at=now)
            elif result.exit_code == 126:
                run.transition("cancelled", "polkit-cancelled", at=now)
                run.recovery_status = "not-required"
            else:
                run.transition("failed", "execution-failed", at=now)
                run.recovery_status = "manual-review-required"
            self.run_store.save(run)
            return run
        finally:
            self._release_lease(run_id)

    def interrupt_run(self, run_id: str, reason: str = "worker-interrupted") -> ActionRun:
        """Record cancellation/crash without retrying or rolling back automatically."""
        held = run_id in self._held_leases
        lease = None if held else self._acquire_lease()
        try:
            run = self.get_run(run_id)
            if run.state not in {"running", "verifying"}:
                raise ActionCenterError(f"Run cannot be interrupted from state: {run.state}")
            run.transition("interrupted", reason, at=self.clock())
            run.recovery_status = "manual-review-required"
            self.run_store.save(run)
            return run
        finally:
            if held:
                self._release_lease(run_id)
            elif lease is not None:
                lease.__exit__(None, None, None)

    def apply(
        self,
        plan_id: str,
        *,
        confirmed: bool,
        accept_no_rollback: bool = False,
        timeout: int = 120,
    ) -> ActionRun:
        """Synchronous CLI wrapper over prepare/execute/complete."""
        prepared = self.prepare_run(
            plan_id,
            confirmed=confirmed,
            accept_no_rollback=accept_no_rollback,
        )
        try:
            result = self.facade.execute(
                prepared.command,
                privileged=prepared.privileged,
                timeout=timeout,
                action_id=prepared.action_id,
                authority="action_center",
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            # Keep an auditable failed run when the execution boundary fails.
            result = ActionResult.fail(f"Execution boundary failed: {exc}", exit_code=-1, action_id=prepared.action_id)
        return self.complete_run(prepared.run_id, result)

    def verify(self, run_id: str) -> ActionRun:
        """Run the definition verifier separately from apply and persist its result."""
        lease = self._acquire_lease()
        try:
            run = self.get_run(run_id)
            if run.state not in {"verifying", "awaiting_reboot"}:
                raise ActionCenterError(f"Run is not awaiting verification: {run.state}")
            if run.state == "awaiting_reboot":
                run.transition("verifying", "verification-resumed", at=self.clock())
            definition = self._definition_for(run.action_id)
            plan = self.get_plan(run.plan_id)
            result = definition.verifier(run, plan, self.runtime)
            return self._complete_verification_locked(run, result)
        finally:
            lease.__exit__(None, None, None)

    def complete_verification(self, run_id: str, result: ActionResult) -> ActionRun:
        """Accept a verifier result produced by an asynchronous trusted worker."""
        lease = self._acquire_lease()
        try:
            run = self.get_run(run_id)
            if run.state != "verifying":
                raise ActionCenterError(f"Run is not awaiting verification: {run.state}")
            return self._complete_verification_locked(run, result)
        finally:
            lease.__exit__(None, None, None)

    def _complete_verification_locked(self, run: ActionRun, result: ActionResult | VerificationDecision) -> ActionRun:
        decision = result if isinstance(result, VerificationDecision) else VerificationDecision(
            "succeeded" if result.success else "failed",
            result.message,
            dict(result.data or {}),
            result.exit_code,
        )
        normalized = decision.to_result(action_id=run.action_id)
        run.verification_result = normalized.to_dict()
        run.verification_attempts += 1
        run.last_verified_at = self.clock()
        run.reboot_required = decision.state == "awaiting_reboot"
        if decision.state == "succeeded":
            run.transition("succeeded", "verification-succeeded", at=self.clock())
            run.recovery_status = "not-required"
        elif decision.state == "awaiting_reboot":
            run.transition("awaiting_reboot", "reboot-required", at=self.clock())
            run.recovery_status = "reboot-required"
        else:
            run.transition("verification_failed", "verification-failed", at=self.clock())
            run.recovery_status = "manual-review-required"
        self.run_store.save(run)
        return run

    def _boot_id(self) -> str:
        reader = getattr(self.runtime, "boot_id", None)
        return str(reader() if callable(reader) else "").strip()

    def _definition_for(self, action_id: str) -> ActionDefinition:
        definition = self.catalog.get(action_id)
        if definition is None:
            raise ActionPlanRejectedError(self.catalog.denied(action_id))
        return definition

    def _host_target_decision(self, target: str) -> PolicyDecision | None:
        """Keep preview hosts read-only even if a caller claims the stable target."""
        version_reader = getattr(self.runtime, "fedora_version", None)
        host_version = str(version_reader() if callable(version_reader) else "").strip()
        if self.release_policy.is_stable_target(target) and self.release_policy.host_is_preview(host_version):
            return PolicyDecision(
                False,
                "host_preview_read_only",
                f"Fedora {host_version} remains read-only until its release policy is certified.",
                f"Use Fedora {self.release_policy.preview_release} preview diagnostics without applying maintenance actions.",
                {"target": target, "host_fedora_version": host_version},
            )
        return None

    def _variant_decision(self, definition: ActionDefinition) -> PolicyDecision | None:
        """Reject an action when its declared Fedora variant excludes this host."""
        variant = "atomic" if self.runtime.is_atomic() else "traditional"
        if variant in definition.supported_variants:
            return None
        reason_code = "atomic_manual_only" if variant == "atomic" else "unsupported_variant"
        return PolicyDecision(
            False,
            reason_code,
            f"{definition.id} is not executable on {variant.title()} Fedora.",
            "Review the action manually or use a supported Fedora variant.",
            {
                "variant": variant,
                "supported_variants": sorted(definition.supported_variants),
            },
        )

    def _render(self, definition: ActionDefinition, parameters: Mapping[str, Any]) -> list[str]:
        vector = [str(part) for part in definition.command_renderer(parameters, self.runtime)]
        if "pkexec" in vector:
            raise CommandValidationError("Canonical Action Center vectors must not contain pkexec.")
        validate_command_vector(vector)
        return vector

    @staticmethod
    def _digest(
        action_id: str,
        parameters: Mapping[str, Any],
        target: str,
        preview: Sequence[str],
        decision: PolicyDecision,
        definition_fields: Mapping[str, Any],
        finding_context: FindingContext | None = None,
    ) -> str:
        payload = {
            "action_id": action_id,
            "parameters": dict(parameters),
            "target": target,
            "preview": list(preview),
            "policy_decision": decision.to_dict(),
            "definition": dict(definition_fields),
        }
        if finding_context is not None:
            payload["finding_context"] = finding_context.to_dict()
        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def _assert_integrity(self, plan: ActionPlan) -> None:
        expected = self._digest(
            plan.action_id,
            plan.parameters,
            plan.target,
            plan.preview,
            plan.policy_decision,
            self._plan_definition_fields(plan),
            plan.finding_context,
        )
        if not plan.digest or expected != plan.digest:
            raise ActionPlanIntegrityError("Action plan digest validation failed.")

    def _definition_fields(self, definition: ActionDefinition, parameters: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "risk_level": definition.risk_level,
            "privileged": self._is_privileged(definition, parameters),
            "confirmation_policy": definition.confirmation_policy,
            "recovery_guidance": definition.recovery_guidance,
            "rollback_supported": definition.rollback_supported,
            "operation_class": definition.operation_class,
            "supported_variants": sorted(definition.supported_variants),
            "reboot_policy": definition.reboot_policy,
            "affected_resources": list(definition.affected_resources),
        }

    def _is_privileged(self, definition: ActionDefinition, parameters: Mapping[str, Any]) -> bool:
        resolver = definition.privilege_resolver
        return bool(resolver(parameters, self.runtime)) if resolver is not None else definition.privileged

    @staticmethod
    def _plan_definition_fields(plan: ActionPlan) -> dict[str, Any]:
        return {
            "risk_level": plan.risk_level,
            "privileged": plan.privileged,
            "confirmation_policy": plan.confirmation_policy,
            "recovery_guidance": plan.recovery_guidance,
            "rollback_supported": plan.rollback_supported,
            "operation_class": plan.operation_class,
            "supported_variants": sorted(plan.supported_variants),
            "reboot_policy": plan.reboot_policy,
            "affected_resources": list(plan.affected_resources),
        }

    def _block_plan(self, plan: ActionPlan, decision: PolicyDecision, *, now: float) -> None:
        plan.policy_decision = decision
        if plan.state != "blocked":
            plan.transition("blocked", decision.reason_code, at=now)
        self.plan_store.save(plan)

    def _acquire_lease(self) -> AbstractContextManager[None]:
        lease = advisory_lock(self.lease_path, timeout=0)
        try:
            lease.__enter__()
        except StateBusyError as exc:
            raise ActionCenterBusyError("Another Action Center operation is active.") from exc
        return lease

    def _release_lease(self, run_id: str) -> None:
        lease = self._held_leases.pop(run_id, None)
        if lease is not None:
            lease.__exit__(None, None, None)

    def _recover_interrupted_if_unleased(self) -> None:
        """Recover only when no live process owns the mutation lease."""
        try:
            lease = self._acquire_lease()
        except ActionCenterBusyError:
            return
        try:
            self.run_store.interrupt_incomplete(now=self.clock())
        finally:
            lease.__exit__(None, None, None)
