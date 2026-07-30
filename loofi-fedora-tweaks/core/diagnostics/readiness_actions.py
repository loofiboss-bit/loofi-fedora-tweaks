"""Safe action planning for release readiness findings."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import cast
from typing import Dict, List, Optional

from core.diagnostics.release_readiness import (
    ReadinessCheck,
    ReleaseReadiness,
    ReleaseReadinessReport,
)
from core.executor.action_executor import ActionExecutor
from core.executor.action_result import ActionResult
from core.fedora_release_policy import FEDORA_RELEASE_POLICY
from services.system.system import SystemManager


@dataclass(frozen=True)
class ReadinessActionCandidate:
    """Reviewable action candidate derived from a readiness finding."""

    id: str
    title: str
    explanation: str
    related_check_id: str
    command_preview: List[str] = field(default_factory=list)
    risk_level: str = "info"
    privileged: bool = False
    manual_only: bool = True
    reversible: bool = True
    preflight_checks: List[str] = field(default_factory=list)
    revert_hint: str = "No automatic rollback is available."
    docs_link: str = ""
    verification_command: List[str] = field(default_factory=list)
    verification_check_id: str = ""
    command: str = ""
    args: List[str] = field(default_factory=list)

    @property
    def executable(self) -> bool:
        """Return True when the candidate can be run by the action bridge."""
        return bool(self.command) and not self.manual_only

    def to_dict(self) -> Dict[str, object]:
        """Serialize for CLI, UI, and support bundle output."""
        return {
            "id": self.id,
            "title": self.title,
            "explanation": self.explanation,
            "related_check_id": self.related_check_id,
            "command_preview": list(self.command_preview),
            "risk_level": self.risk_level,
            "privileged": self.privileged,
            "manual_only": self.manual_only,
            "reversible": self.reversible,
            "preflight_checks": list(self.preflight_checks),
            "revert_hint": self.revert_hint,
            "docs_link": self.docs_link,
            "verification_command": list(self.verification_command),
            "verification_check_id": self.verification_check_id,
            "executable": self.executable,
        }


@dataclass
class ReadinessActionPlan:
    """Action inbox generated from a release readiness report."""

    target: str
    generated_at: float
    candidates: List[ReadinessActionCandidate] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "target": self.target,
            "generated_at": self.generated_at,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "count": len(self.candidates),
        }


class ReadinessActionService:
    """Bridge read-only readiness findings to explicit, confirmed actions."""

    DEFAULT_TARGET = FEDORA_RELEASE_POLICY.stable_target
    EXECUTABLE_REPO_ACTION_ID = "readiness-repo-cache-clean"
    _ACTION_CENTER_ADAPTERS = {
        EXECUTABLE_REPO_ACTION_ID: "dnf-clean-all",
    }

    @classmethod
    def build_plan(
        cls,
        target_key: str = DEFAULT_TARGET,
        report: Optional[ReleaseReadinessReport] = None,
    ) -> ReadinessActionPlan:
        """Build an action plan without mutating the system."""
        report = report or ReleaseReadiness.run(target_key)
        candidates = [
            candidate
            for check in report.checks
            for candidate in cls._candidate_for_check(check)
        ]
        return ReadinessActionPlan(
            target=report.target,
            generated_at=time.time(),
            candidates=candidates,
        )

    @classmethod
    def get_candidate(
        cls,
        action_id: str,
        target_key: str = DEFAULT_TARGET,
        report: Optional[ReleaseReadinessReport] = None,
    ) -> Optional[ReadinessActionCandidate]:
        """Return one candidate by ID."""
        plan = cls.build_plan(target_key=target_key, report=report)
        return next((candidate for candidate in plan.candidates if candidate.id == action_id), None)

    @classmethod
    def preview(
        cls,
        action_id: str,
        target_key: str = DEFAULT_TARGET,
        report: Optional[ReleaseReadinessReport] = None,
        executor: Optional[ActionExecutor] = None,
    ) -> ActionResult:
        """Preview an action without executing it."""
        candidate = cls.get_candidate(action_id, target_key=target_key, report=report)
        if candidate is None:
            return ActionResult.fail(f"Readiness action not found: {action_id}", action_id=action_id)

        data = {"candidate": candidate.to_dict()}
        canonical_id = cls._ACTION_CENTER_ADAPTERS.get(candidate.id)
        if canonical_id:
            from core.actions import ActionCenterOrchestrator

            orchestrator = ActionCenterOrchestrator()
            plan = orchestrator.plan(canonical_id, target=target_key)
            result = cast(ActionResult, orchestrator.preview(plan.plan_id))
            result.data = {
                **(result.data or {}),
                **data,
                "compatibility_adapter": candidate.id,
            }
            return result
        if not candidate.executable:
            return ActionResult(
                success=True,
                message=f"[PREVIEW] Manual-only action: {candidate.title}",
                preview=True,
                data=data,
                action_id=candidate.id,
            )

        runner = executor or ActionExecutor()
        result = runner.preview(
            candidate.command,
            candidate.args,
            privileged=candidate.privileged,
            action_id=candidate.id,
        )
        result.data = {**(result.data or {}), **data}
        return result

    @classmethod
    def run(
        cls,
        action_id: str,
        *,
        target_key: str = DEFAULT_TARGET,
        confirm: bool = False,
        report: Optional[ReleaseReadinessReport] = None,
        executor: Optional[ActionExecutor] = None,
    ) -> ActionResult:
        """Compatibility handoff that creates a plan and never applies it."""
        candidate = cls.get_candidate(action_id, target_key=target_key, report=report)
        if candidate is None:
            return ActionResult.fail(f"Readiness action not found: {action_id}", action_id=action_id)
        if candidate.manual_only:
            return ActionResult.fail(
                "Manual-only readiness actions cannot be converted into executable plans.",
                data={"candidate": candidate.to_dict()},
                action_id=candidate.id,
            )
        if not candidate.command:
            return ActionResult.fail(
                "Readiness action has no closed Action Center definition.",
                data={"candidate": candidate.to_dict()},
                action_id=candidate.id,
            )

        canonical_id = cls._ACTION_CENTER_ADAPTERS.get(candidate.id)
        if canonical_id:
            from core.actions import ActionCenterOrchestrator

            orchestrator = ActionCenterOrchestrator()
            plan = orchestrator.plan(canonical_id, target=target_key)
            return ActionResult(
                success=True,
                message="Action Center review plan created; no host change was applied.",
                action_id=candidate.id,
                data={
                    "candidate": candidate.to_dict(),
                    "plan": plan.to_dict(),
                    "policy_decision": plan.policy_decision.to_dict(),
                    "compatibility_adapter": candidate.id,
                    "plan_id": plan.plan_id,
                    "definition_id": plan.action_id,
                    "state": plan.state,
                    "review_required": True,
                    "auto_apply": False,
                    "next_action": (
                        f"loofi-fedora-tweaks --cli action-center apply {plan.plan_id} --confirm"
                    ),
                    "deprecated_confirm_ignored": bool(confirm),
                },
            )

        # Non-audited legacy definitions are never promoted to v14 execution.
        return ActionResult.fail(
            "This legacy readiness action is manual-only in the v14 deny-by-default catalog.",
            action_id=candidate.id,
            data={"candidate": candidate.to_dict(), "compatibility_adapter": candidate.id},
        )

    @classmethod
    def verify(
        cls,
        action_id: str,
        target_key: str = DEFAULT_TARGET,
        report: Optional[ReleaseReadinessReport] = None,
    ) -> ActionResult:
        """Verify an action by rerunning the related readiness check."""
        candidate = cls.get_candidate(action_id, target_key=target_key, report=report)
        if candidate is None:
            return ActionResult.fail(f"Readiness action not found: {action_id}", action_id=action_id)

        canonical_id = cls._ACTION_CENTER_ADAPTERS.get(candidate.id)
        if canonical_id:
            from core.actions import ActionCenterOrchestrator, ActionRunStore

            awaiting = next(
                (
                    run
                    for run in reversed(ActionRunStore().list(limit=100))
                    if run.action_id == canonical_id and run.state == "verifying"
                ),
                None,
            )
            if awaiting is None:
                return ActionResult.fail(
                    "No completed execution is awaiting verification for this readiness action.",
                    action_id=candidate.id,
                    data={"candidate": candidate.to_dict(), "compatibility_adapter": candidate.id},
                )
            verified = ActionCenterOrchestrator().verify(awaiting.run_id)
            return ActionResult(
                success=verified.state == "succeeded",
                message=(verified.verification_result or {}).get("message", "Verification failed."),
                exit_code=(verified.verification_result or {}).get("exit_code"),
                action_id=candidate.id,
                data={
                    "candidate": candidate.to_dict(),
                    "run": verified.to_dict(),
                    "compatibility_adapter": candidate.id,
                },
            )

        fresh_report = report or ReleaseReadiness.run(target_key)
        check_id = candidate.verification_check_id or candidate.related_check_id
        check = next((item for item in fresh_report.checks if item.id == check_id), None)
        if check is None:
            return ActionResult.fail(
                f"Verification check not found: {check_id}",
                data={"candidate": candidate.to_dict()},
                action_id=candidate.id,
            )

        healthy = check.severity not in {"warning", "error", "critical"}
        return ActionResult(
            success=healthy,
            message=f"{check.title}: {check.summary}",
            data={
                "candidate": candidate.to_dict(),
                "verification_check": check.to_dict(advanced=False),
            },
            action_id=candidate.id,
        )

    @classmethod
    def _candidate_for_check(cls, check: ReadinessCheck) -> List[ReadinessActionCandidate]:
        if check.recommendation is None:
            return []
        if check.id == "repo-health" and check.status != "pass":
            return [cls._repo_health_candidate(check)]
        return [cls._manual_candidate(check)]

    @classmethod
    def _repo_health_candidate(cls, check: ReadinessCheck) -> ReadinessActionCandidate:
        recommendation = check.recommendation
        assert recommendation is not None
        command, args = cls._package_cache_command()
        command_preview = ["pkexec", command] + args
        return ReadinessActionCandidate(
            id=cls.EXECUTABLE_REPO_ACTION_ID,
            title="Clean package metadata cache",
            explanation=(
                "Clear local package metadata so the next repository query starts from "
                "fresh Fedora 44 metadata. This does not install, remove, or upgrade packages."
            ),
            related_check_id=check.id,
            command_preview=command_preview,
            risk_level="low",
            privileged=True,
            manual_only=False,
            reversible=True,
            preflight_checks=[
                "Confirm no package manager operation is currently running.",
                "Review enabled third-party repositories before retrying release work.",
            ],
            revert_hint="Package metadata cache is rebuilt automatically on the next package-manager query.",
            docs_link=recommendation.docs_link,
            verification_command=check.command_preview or [],
            verification_check_id=check.id,
            command=command,
            args=args,
        )

    @staticmethod
    def _manual_candidate(check: ReadinessCheck) -> ReadinessActionCandidate:
        recommendation = check.recommendation
        assert recommendation is not None
        return ReadinessActionCandidate(
            id=f"readiness-{check.id}",
            title=recommendation.title,
            explanation=recommendation.description,
            related_check_id=check.id,
            command_preview=list(recommendation.command_preview or check.command_preview or []),
            risk_level=recommendation.risk_level,
            privileged=False,
            manual_only=True,
            reversible=recommendation.reversible,
            preflight_checks=[],
            revert_hint=recommendation.rollback_hint,
            docs_link=recommendation.docs_link,
            verification_command=check.command_preview or [],
            verification_check_id=check.id,
        )

    @staticmethod
    def _package_cache_command() -> tuple[str, List[str]]:
        package_manager = SystemManager.get_package_manager()
        if package_manager == "rpm-ostree":
            return package_manager, ["cleanup", "--base"]
        return package_manager, ["clean", "all"]
