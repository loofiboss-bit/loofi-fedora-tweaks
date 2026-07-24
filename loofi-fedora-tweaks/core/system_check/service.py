"""Bounded orchestration for the closed, read-only System Check profile."""

from __future__ import annotations

import re
import threading
import time
import uuid
from collections.abc import Callable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, cast

from core.actions.stores import ActionPlanStore, ActionRunStore
from core.diagnostics.daily_maintenance import DailyMaintenanceService, MaintenanceCard
from core.observability.privacy import redact_payload
from core.observability.snapshot import HealthSnapshot
from core.observability.timeline import HealthTimelineStore
from core.state.doctor import StateDoctor
from core.system_check.mappings import mapped_action, validate_finding, validate_mappings
from core.system_check.models import (
    CheckProgress,
    CheckProgressStage,
    CheckSourceError,
    CheckState,
    FindingEvidence,
    FindingSeverity,
    SupportedVariant,
    SystemCheckResult,
    SystemFinding,
)
from services.storage.reclaim import ReclaimProbeService
from services.system.system import SystemManager

Collector = Callable[[bool, float], tuple[SystemFinding, ...]]
ProgressCallback = Callable[[CheckProgress], None]
QUICK_PROFILE_ID = "system-check-quick-v1"
FIXTURE_PROFILE_ID = "system-check-fixture-v1"
QUICK_PROFILE_SOURCES = (
    "state-integrity",
    "maintenance",
    "storage-reclaim",
    "action-center",
    "pending-reboot",
)
_ALL_VARIANTS: frozenset[SupportedVariant] = frozenset({"traditional", "atomic"})
_UNIT_PATTERN = re.compile(r"^[A-Za-z0-9_.@:-]+$")
_PACKAGE_RECLAIM_THRESHOLD = 512 * 1024 * 1024
_JOURNAL_RECLAIM_THRESHOLD = 1024 * 1024 * 1024


@dataclass(frozen=True)
class CollectorSpec:
    """One named member of the explicit quick profile."""

    source_id: str
    timeout_seconds: float
    collect: Collector


class SystemCheckService:
    """Compose existing trusted probes with partial and cancellation semantics."""

    def __init__(
        self,
        *,
        collectors: Sequence[CollectorSpec] | None = None,
        timeline_store: HealthTimelineStore | None = None,
        state_doctor: StateDoctor | None = None,
        maintenance_service: DailyMaintenanceService | None = None,
        reclaim_service: ReclaimProbeService | None = None,
        plan_store: ActionPlanStore | None = None,
        run_store: ActionRunStore | None = None,
        system_manager: type[SystemManager] = SystemManager,
        clock: Callable[[], float] = time.time,
        monotonic: Callable[[], float] = time.monotonic,
    ):
        self.timeline_store = timeline_store or HealthTimelineStore()
        self.state_doctor = state_doctor or StateDoctor()
        self.maintenance_service = maintenance_service or DailyMaintenanceService()
        self.reclaim_service = reclaim_service or ReclaimProbeService()
        self.plan_store = plan_store or ActionPlanStore()
        self.run_store = run_store or ActionRunStore()
        self.system_manager = system_manager
        self.clock = clock
        self.monotonic = monotonic
        self.profile_id = FIXTURE_PROFILE_ID if collectors is not None else QUICK_PROFILE_ID
        self.collectors = tuple(collectors or self._default_collectors())
        self._validate_profile()

    def _default_collectors(self) -> tuple[CollectorSpec, ...]:
        return (
            CollectorSpec("state-integrity", 20.0, self._collect_state),
            CollectorSpec("maintenance", 45.0, self._collect_maintenance),
            CollectorSpec("storage-reclaim", 25.0, self._collect_reclaim),
            CollectorSpec("action-center", 10.0, self._collect_action_center),
            CollectorSpec("pending-reboot", 20.0, self._collect_pending_reboot),
        )

    def _validate_profile(self) -> None:
        source_ids = [item.source_id for item in self.collectors]
        if not source_ids or len(source_ids) != len(set(source_ids)):
            raise ValueError("System Check profile requires unique, closed collectors.")
        if self.profile_id == QUICK_PROFILE_ID and tuple(source_ids) != QUICK_PROFILE_SOURCES:
            raise ValueError("The production quick profile cannot be extended or reordered.")
        if any(item.timeout_seconds <= 0 for item in self.collectors):
            raise ValueError("Every System Check collector requires a positive timeout.")
        validate_mappings()

    def run(
        self,
        *,
        cancel_event: threading.Event | None = None,
        persist: bool = True,
        progress_callback: ProgressCallback | None = None,
    ) -> SystemCheckResult:
        """Run the explicit profile; cancelled and wholly failed checks are not stored."""
        cancellation = cancel_event or threading.Event()
        started_at = self.clock()
        atomic = bool(self.system_manager.is_atomic())
        check_id = str(uuid.uuid4())
        findings: list[SystemFinding] = []
        errors: list[CheckSourceError] = []
        durations: dict[str, float] = {}
        completed_sources: list[str] = []
        cancelled_sources: list[str] = []
        worker_starts: dict[str, float] = {}
        starts_lock = threading.Lock()
        announced_sources: set[str] = set()
        last_progress_at = self.monotonic()

        def emit_progress(source_id: str, stage: CheckProgressStage) -> None:
            if progress_callback is None:
                return
            unavailable = tuple(sorted(error.source_id for error in errors))
            progress = CheckProgress(
                source_id=source_id,
                stage=stage,
                completed_sources=len(completed_sources) + len(errors),
                total_sources=len(self.collectors),
                elapsed_seconds=max(0.0, self.monotonic() - worker_started_at),
                unavailable_sources=unavailable,
            )
            try:
                progress_callback(progress)
            except (RuntimeError, TypeError, ValueError):
                return

        def invoke(spec: CollectorSpec) -> tuple[SystemFinding, ...]:
            with starts_lock:
                worker_starts[spec.source_id] = self.monotonic()
            return spec.collect(atomic, self.clock())

        worker_started_at = self.monotonic()
        executor = ThreadPoolExecutor(max_workers=min(4, len(self.collectors)), thread_name_prefix="system-check")
        futures: dict[Future[tuple[SystemFinding, ...]], CollectorSpec] = {
            executor.submit(invoke, spec): spec for spec in self.collectors
        }
        pending = set(futures)
        cancelled = False
        try:
            while pending:
                if cancellation.is_set():
                    cancelled = True
                    emit_progress("", "cancelling")
                    for future in pending:
                        spec = futures[future]
                        if future.cancel():
                            cancelled_sources.append(spec.source_id)
                    cancelled_sources.extend(
                        futures[future].source_id
                        for future in pending
                        if futures[future].source_id not in cancelled_sources
                    )
                    break
                now = self.monotonic()
                with starts_lock:
                    newly_started = sorted(set(worker_starts) - announced_sources)
                for source_id in newly_started:
                    announced_sources.add(source_id)
                    emit_progress(source_id, "running")
                for future in tuple(pending):
                    spec = futures[future]
                    if future.done():
                        pending.remove(future)
                        began = worker_starts.get(spec.source_id)
                        if began is None:
                            began = now
                        duration = max(0.0, (now - began) * 1000.0)
                        durations[spec.source_id] = duration
                        try:
                            collected = future.result()
                            for finding in collected:
                                validate_finding(finding)
                            findings.extend(collected)
                            completed_sources.append(spec.source_id)
                            emit_progress(spec.source_id, "completed")
                        except Exception as exc:  # noqa: BLE001 - collector isolation boundary
                            errors.append(CheckSourceError(
                                spec.source_id,
                                "collector-failed",
                                str(redact_payload(str(exc))),
                                duration,
                            ))
                            emit_progress(spec.source_id, "failed")
                        continue
                    began = worker_starts.get(spec.source_id)
                    if began is not None and now - began >= spec.timeout_seconds:
                        pending.remove(future)
                        future.cancel()
                        duration = max(0.0, (now - began) * 1000.0)
                        durations[spec.source_id] = duration
                        errors.append(CheckSourceError(
                            spec.source_id,
                            "collector-timeout",
                            "Collector exceeded its bounded timeout.",
                            duration,
                            timed_out=True,
                        ))
                        emit_progress(spec.source_id, "timed_out")
                if pending and now - last_progress_at >= 0.25:
                    active = sorted(
                        source_id
                        for source_id in announced_sources
                        if source_id not in completed_sources
                        and source_id not in {error.source_id for error in errors}
                    )
                    emit_progress(active[0] if active else "", "running")
                    last_progress_at = now
                if pending:
                    cancellation.wait(0.01)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        completed_at = self.clock()
        if cancelled:
            result = SystemCheckResult(
                check_id,
                self.profile_id,
                "cancelled",
                atomic,
                started_at,
                completed_at,
                tuple(sorted(findings, key=lambda item: item.fingerprint)),
                tuple(errors),
                tuple(sorted(durations.items())),
                tuple(sorted(completed_sources)),
                tuple(sorted(set(cancelled_sources))),
            )
        else:
            state: CheckState = "failed" if errors and not completed_sources else ("partial" if errors else "completed")
            result = SystemCheckResult(
                check_id,
                self.profile_id,
                state,
                atomic,
                started_at,
                completed_at,
                tuple(sorted(findings, key=lambda item: item.fingerprint)),
                tuple(errors),
                tuple(sorted(durations.items())),
                tuple(sorted(completed_sources)),
            )
        if persist and result.state in {"completed", "partial"}:
            self.timeline_store.append(HealthSnapshot.from_system_check(result))
        return result

    @staticmethod
    def _evidence(source_id: str, facts: dict[str, Any], collected_at: float) -> FindingEvidence:
        return FindingEvidence.from_mapping(source_id, facts, collected_at=collected_at)

    def _collect_state(self, _atomic: bool, collected_at: float) -> tuple[SystemFinding, ...]:
        report = self.state_doctor.run()
        findings = []
        for item in report.get("findings", []):
            if not isinstance(item, dict):
                continue
            severity: FindingSeverity = "critical" if item.get("severity") == "error" else "attention"
            facts = {
                "domain": str(item.get("domain", "")),
                "summary": str(item.get("summary", "")),
                "evidence": str(item.get("evidence", "")),
            }
            findings.append(SystemFinding.build(
                finding_id="state-integrity",
                category="application-state",
                severity=severity,
                title="Application state needs review",
                summary=facts["summary"],
                evidence=self._evidence("state-integrity", facts, collected_at),
                applicable_variants=_ALL_VARIANTS,
                freshness_state="fresh",
                affected_resources=(f"state:{facts['domain']}",),
                route_id="settings:repair",
                manual_guidance=str(item.get("next_step", "")) or "Review the affected state without overwriting it.",
                manual_reason_code="state-integrity-review",
            ))
        return tuple(findings)

    def _collect_maintenance(self, atomic: bool, collected_at: float) -> tuple[SystemFinding, ...]:
        report = self.maintenance_service.collect_quick()
        if report.atomic != atomic:
            raise RuntimeError("Maintenance collector returned a conflicting Fedora variant.")
        findings: list[SystemFinding] = []
        for card in report.cards:
            findings.extend(self._findings_from_card(card, atomic, collected_at))
        return tuple(findings)

    def _findings_from_card(
        self,
        card: MaintenanceCard,
        atomic: bool,
        collected_at: float,
    ) -> list[SystemFinding]:
        variant: frozenset[SupportedVariant] = frozenset({"atomic" if atomic else "traditional"})
        if card.id == "failed-services" and card.state != "success":
            findings = []
            for service in _failed_service_units(card.details):
                facts = {"service": service, "state": card.state}
                action_id, parameters = mapped_action("failed-service", facts, atomic=atomic)
                findings.append(SystemFinding.build(
                    finding_id="failed-service",
                    category="services",
                    severity="attention",
                    title="Failed service",
                    summary=f"{service} is in the failed service list.",
                    evidence=self._evidence("maintenance", facts, collected_at),
                    applicable_variants=_ALL_VARIANTS,
                    freshness_state="fresh",
                    affected_resources=(f"systemd-unit:{service}",),
                    action_id=action_id,
                    action_parameters=parameters,
                    route_id="maintenance:action-center",
                    manual_guidance="" if action_id else "Inspect the exact unit and its journal before changing it.",
                    manual_reason_code="" if action_id else "failed-service-manual-review",
                ))
            return findings
        if card.id == "disk-usage":
            usage = _root_usage_percent(card.details)
            if card.state == "error" or (usage is not None and usage >= 90):
                disk_facts: dict[str, Any] = {"root_usage_percent": usage, "state": card.state}
                return [SystemFinding.build(
                    finding_id="root-disk-pressure",
                    category="storage",
                    severity="critical" if usage is not None and usage >= 95 else "attention",
                    title="Root filesystem needs attention",
                    summary=card.summary,
                    evidence=self._evidence("maintenance", disk_facts, collected_at),
                    applicable_variants=_ALL_VARIANTS,
                    freshness_state="fresh",
                    affected_resources=("filesystem:/",),
                    route_id="maintenance:cleanup",
                    manual_guidance="Review the read-only reclaim preview before removing any data.",
                    manual_reason_code="root-disk-pressure-review",
                )]
        if card.id in {"system-updates", "package-health"} and card.state in {"warning", "error", "blocked"}:
            facts = {"card_id": card.id, "state": card.state, "summary": card.summary}
            return [SystemFinding.build(
                finding_id="package-health",
                category="updates",
                severity="critical" if card.state in {"error", "blocked"} else "attention",
                title="Package and update health needs review",
                summary=card.summary,
                evidence=self._evidence("maintenance", facts, collected_at),
                applicable_variants=variant,
                freshness_state="fresh",
                affected_resources=("package-manager",),
                route_id="maintenance:updates",
                manual_guidance="Resolve active locks or repository errors before starting package work.",
                manual_reason_code="package-health-review",
            )]
        if card.id == "rollback" and card.state == "warning":
            facts = {"state": card.state, "summary": card.summary}
            return [SystemFinding.build(
                finding_id="recovery-protection",
                category="recovery",
                severity="attention",
                title="Recovery protection is limited",
                summary=card.summary,
                evidence=self._evidence("maintenance", facts, collected_at),
                applicable_variants=variant,
                freshness_state="fresh",
                affected_resources=("recovery",),
                route_id="backup",
                manual_guidance="Review a supported backup or snapshot workflow before high-risk maintenance.",
                manual_reason_code="recovery-protection-review",
            )]
        return []

    def _collect_reclaim(self, atomic: bool, collected_at: float) -> tuple[SystemFinding, ...]:
        analysis = self.reclaim_service.analyze()
        if analysis.atomic != atomic:
            raise RuntimeError("Reclaim collector returned a conflicting Fedora variant.")
        findings: list[SystemFinding] = []
        for category in analysis.categories:
            estimated = category.estimated_bytes
            if category.id == "package-cache" and not atomic and estimated is not None and estimated >= _PACKAGE_RECLAIM_THRESHOLD:
                facts = {"category": category.id, "estimated_bytes": estimated}
                action_id, parameters = mapped_action("reclaimable-package-cache", facts, atomic=False)
                findings.append(SystemFinding.build(
                    finding_id="reclaimable-package-cache",
                    category="storage",
                    severity="attention",
                    title="Package metadata cache can be reclaimed",
                    summary=f"At least {estimated} bytes of package metadata are reclaimable.",
                    evidence=self._evidence("storage-reclaim", facts, collected_at),
                    applicable_variants=frozenset({"traditional"}),
                    freshness_state="fresh",
                    affected_resources=("package-cache",),
                    action_id=action_id,
                    action_parameters=parameters,
                    route_id="maintenance:action-center",
                ))
            elif category.id == "journal" and estimated is not None and estimated >= _JOURNAL_RECLAIM_THRESHOLD:
                facts = {"category": category.id, "estimated_bytes": estimated}
                findings.append(SystemFinding.build(
                    finding_id="large-system-journal",
                    category="storage",
                    severity="attention",
                    title="System journal is large",
                    summary=f"The journal uses approximately {estimated} bytes.",
                    evidence=self._evidence("storage-reclaim", facts, collected_at),
                    applicable_variants=_ALL_VARIANTS,
                    freshness_state="fresh",
                    affected_resources=("system-journal",),
                    route_id="maintenance:cleanup",
                    manual_guidance=category.guidance,
                    manual_reason_code="large-system-journal-review",
                ))
        return tuple(findings)

    def _collect_action_center(self, _atomic: bool, collected_at: float) -> tuple[SystemFinding, ...]:
        plans = self.plan_store.list_read_only()
        runs = self.run_store.list_read_only()
        findings: list[SystemFinding] = []
        for plan in plans:
            if plan.state not in {"blocked", "needs_review"}:
                continue
            facts = {"action_id": plan.action_id, "plan_id": plan.plan_id, "state": plan.state}
            findings.append(SystemFinding.build(
                finding_id="action-plan-needs-review",
                category="action-center",
                severity="attention",
                title="Action plan needs review",
                summary=f"{plan.action_id} is {plan.state.replace('_', ' ')}.",
                evidence=self._evidence("action-center", facts, collected_at),
                applicable_variants=cast(frozenset[SupportedVariant], plan.supported_variants),
                freshness_state="fresh",
                affected_resources=tuple(plan.affected_resources),
                route_id="maintenance:action-center",
                manual_guidance="Review the persisted plan and create a fresh preview before execution.",
                manual_reason_code="action-plan-review",
            ))
        for run in runs:
            if run.state not in {"failed", "verification_failed", "interrupted"}:
                continue
            facts = {"action_id": run.action_id, "run_id": run.run_id, "state": run.state}
            findings.append(SystemFinding.build(
                finding_id="action-run-needs-review",
                category="action-center",
                severity="critical" if run.state == "verification_failed" else "attention",
                title="Action run needs review",
                summary=f"{run.action_id} ended as {run.state.replace('_', ' ')}.",
                evidence=self._evidence("action-center", facts, collected_at),
                applicable_variants=cast(frozenset[SupportedVariant], run.supported_variants),
                freshness_state="fresh",
                affected_resources=tuple(run.affected_resources),
                route_id="maintenance:action-center",
                manual_guidance="Review verification and recovery evidence; never retry automatically.",
                manual_reason_code="action-run-review",
            ))
        return tuple(findings)

    def _collect_pending_reboot(self, atomic: bool, collected_at: float) -> tuple[SystemFinding, ...]:
        if not atomic or not self.system_manager.has_pending_deployment():
            return ()
        facts = {"pending_deployment": True}
        return (SystemFinding.build(
            finding_id="pending-reboot",
            category="updates",
            severity="attention",
            title="Atomic deployment awaits reboot",
            summary="An rpm-ostree deployment is staged and needs a reboot.",
            evidence=self._evidence("pending-reboot", facts, collected_at),
            applicable_variants=frozenset({"atomic"}),
            freshness_state="fresh",
            affected_resources=("rpm-ostree-deployment",),
            route_id="maintenance:updates",
            manual_guidance="Save work and review the staged deployment before rebooting.",
            manual_reason_code="pending-deployment-reboot",
        ),)


def _root_usage_percent(details: str) -> float | None:
    percentages = re.findall(r"\b(\d{1,3})%\b", str(details))
    return float(percentages[-1]) if percentages else None


def _failed_service_units(details: str) -> tuple[str, ...]:
    units: list[str] = []
    for line in str(details).splitlines():
        for token in line.replace("●", " ").split():
            if _UNIT_PATTERN.fullmatch(token) and ("." in token or "@" in token):
                units.append(token)
                break
    return tuple(dict.fromkeys(units))
