"""Typed, conservative Outcome Evidence for Action Center runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

from core.actions.contracts import ActionPlan, ActionRun
from core.privacy import redact_payload, redact_text

EvidenceQuality = Literal["authoritative", "partial", "unavailable", "stale"]
OutcomeState = Literal[
    "verified",
    "awaiting_reboot",
    "partially_verified",
    "verification_failed",
    "unverified",
    "blocked",
    "failed",
    "interrupted",
    "cancelled",
]


@dataclass(frozen=True)
class EvidenceFact:
    """One redacted, source-labelled fact; absence is never inferred."""

    key: str
    value: Any
    source: str
    quality: EvidenceQuality = "authoritative"
    observed_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = redact_payload({"value": self.value})
        return {
            "key": redact_text(self.key, limit=80),
            "value": payload.get("value"),
            "source": redact_text(self.source, limit=120),
            "quality": self.quality,
            "observed_at": self.observed_at,
        }


@dataclass(frozen=True)
class RecoveryReadiness:
    """Recorded recovery capability, never an executable rollback command."""

    available: bool
    status: str
    guidance: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "status": redact_text(self.status, limit=80),
            "guidance": redact_text(self.guidance, limit=500),
        }


@dataclass(frozen=True)
class OutcomeSummary:
    """Complete bounded classification for one action request."""

    action_id: str
    plan_id: str
    run_id: str
    correlation_id: str
    state: OutcomeState
    reason: str
    expected: tuple[EvidenceFact, ...] = ()
    before: tuple[EvidenceFact, ...] = ()
    after: tuple[EvidenceFact, ...] = ()
    verification: tuple[EvidenceFact, ...] = ()
    affected_resources: tuple[str, ...] = ()
    source_quality: EvidenceQuality = "authoritative"
    reboot_required: bool = False
    recovery: RecoveryReadiness = field(default_factory=lambda: RecoveryReadiness(False, "unavailable"))
    recorded_at: float = 0.0
    verified_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "loofi.outcome-evidence/v1",
            "action_id": self.action_id,
            "plan_id": self.plan_id,
            "run_id": self.run_id,
            "correlation_id": self.correlation_id,
            "state": self.state,
            "reason": redact_text(self.reason, limit=500),
            "expected": [fact.to_dict() for fact in self.expected],
            "before": [fact.to_dict() for fact in self.before],
            "after": [fact.to_dict() for fact in self.after],
            "verification": [fact.to_dict() for fact in self.verification],
            "affected_resources": list(self.affected_resources),
            "source_quality": self.source_quality,
            "reboot_required": self.reboot_required,
            "recovery": self.recovery.to_dict(),
            "recorded_at": self.recorded_at,
            "verified_at": self.verified_at,
        }


class OutcomeEvidenceComposer:
    """Compose evidence from recorded Action Center objects only."""

    def compose(
        self,
        plan: ActionPlan,
        run: ActionRun | None = None,
        *,
        before_facts: Mapping[str, Any] | None = None,
        after_facts: Mapping[str, Any] | None = None,
        source_quality: EvidenceQuality = "authoritative",
    ) -> OutcomeSummary:
        state = self._state(plan, run)
        reason = self._reason(plan, run)
        expected = (
            EvidenceFact("action", plan.action_id, "action_center.plan"),
            EvidenceFact("target", plan.target, "action_center.plan"),
            EvidenceFact("risk_level", plan.risk_level, "action_center.plan"),
            EvidenceFact("expected_change", plan.policy_decision.explanation, "action_center.plan"),
        )
        verification = self._result_facts(run.verification_result if run else None, "verification")
        recovery = RecoveryReadiness(
            bool(plan.rollback_supported),
            "action_center" if plan.rollback_supported else "manual_guidance" if plan.recovery_guidance else "unavailable",
            plan.recovery_guidance,
        )
        resources = tuple(dict.fromkeys(str(item)[:160] for item in plan.affected_resources if str(item).strip()))
        return OutcomeSummary(
            action_id=plan.action_id,
            plan_id=plan.plan_id,
            run_id=str(getattr(run, "run_id", "") or ""),
            correlation_id=str(getattr(run, "correlation_id", "") or ""),
            state=state,
            reason=reason,
            expected=expected,
            before=self._facts_from_mapping(before_facts or {}, "recorded.before", source_quality),
            after=self._facts_from_mapping(after_facts or {}, "recorded.after", source_quality),
            verification=verification,
            affected_resources=resources,
            source_quality=source_quality,
            reboot_required=bool(getattr(run, "reboot_required", False)) or state == "awaiting_reboot",
            recovery=recovery,
            recorded_at=float(getattr(run, "created_at", plan.created_at) or plan.created_at),
            verified_at=getattr(run, "last_verified_at", None),
        )

    @staticmethod
    def _state(plan: ActionPlan, run: ActionRun | None) -> OutcomeState:
        if run is None:
            return "blocked" if plan.state == "blocked" else "unverified"
        mapping: dict[str, OutcomeState] = {
            "succeeded": "verified",
            "awaiting_reboot": "awaiting_reboot",
            "verification_failed": "verification_failed",
            "failed": "failed",
            "interrupted": "interrupted",
            "cancelled": "cancelled",
            "verifying": "partially_verified" if run.execution_result else "unverified",
            "running": "unverified",
        }
        return mapping.get(run.state, "unverified")

    @staticmethod
    def _reason(plan: ActionPlan, run: ActionRun | None) -> str:
        if run is not None and run.state_history:
            latest = run.state_history[-1]
            if latest.get("reason"):
                return str(latest["reason"])
        if run is not None and run.verification_result and run.verification_result.get("message"):
            return str(run.verification_result["message"])
        if plan.policy_decision.reason_code:
            return f"{plan.policy_decision.reason_code}: {plan.policy_decision.explanation}"
        return "Outcome has not been independently classified."

    @staticmethod
    def _result_facts(result: Mapping[str, Any] | None, prefix: str) -> tuple[EvidenceFact, ...]:
        if not isinstance(result, Mapping):
            return ()
        keys = ("success", "exit_code", "message", "needs_reboot", "verification_state")
        return tuple(
            EvidenceFact(key, result[key], f"action_center.{prefix}")
            for key in keys
            if key in result
        )

    @staticmethod
    def _facts_from_mapping(
        values: Mapping[str, Any], source: str, quality: EvidenceQuality
    ) -> tuple[EvidenceFact, ...]:
        return tuple(
            EvidenceFact(str(key)[:80], value, source, quality)
            for key, value in list(values.items())[:32]
        )
