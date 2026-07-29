"""Explicit, bounded orchestration for the Compass troubleshooting journey."""

from __future__ import annotations

import logging
import shutil
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from core.troubleshooting.adapters import (
    SourceEvidence,
    adapt_action_center,
    adapt_change_journal,
    adapt_observability,
    adapt_structured_source,
    adapt_system_check,
)
from core.troubleshooting.comparison import compare_sessions
from core.troubleshooting.composition import compose_session
from core.troubleshooting.lifecycle import (
    CancellationSignal,
    new_session,
    start_session,
)
from core.troubleshooting.models import (
    NextStep,
    SupportedVariant,
    TroubleshootingComparison,
    TroubleshootingFinding,
    TroubleshootingSession,
)
from core.troubleshooting.profiles import SourceBudget, require_profile
from core.troubleshooting.storage import TroubleshootingSessionStore
from services.system.system import SystemManager

logger = logging.getLogger(__name__)

ProgressCallback = Callable[["TroubleshootingProgress"], None]
VariantResolver = Callable[[], SupportedVariant]


@dataclass(frozen=True)
class TroubleshootingProgress:
    """One privacy-safe source progress update."""

    source_id: str
    state: str
    completed_sources: int
    total_sources: int
    elapsed_seconds: float

    @property
    def percentage(self) -> int:
        if self.total_sources <= 0:
            return 0
        return max(0, min(100, int(self.completed_sources * 100 / self.total_sources)))


@dataclass(frozen=True)
class TroubleshootingRun:
    """Terminal session plus optional compatible follow-up and store warning."""

    session: TroubleshootingSession
    comparison: TroubleshootingComparison | None = None
    persistence_reason_code: str = ""


class EvidenceCollector(Protocol):
    """Source-owned collection boundary used only after explicit activation."""

    def collect(
        self,
        source_id: str,
        session: TroubleshootingSession,
        *,
        started_at: float,
        cancellation: CancellationSignal,
    ) -> SourceEvidence:
        ...


class DefaultEvidenceCollector:
    """Reuse existing bounded readers without adding execution authority."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.time,
        resolv_conf: Path = Path("/etc/resolv.conf"),
    ) -> None:
        self.clock = clock
        self.resolv_conf = resolv_conf

    def collect(
        self,
        source_id: str,
        session: TroubleshootingSession,
        *,
        started_at: float,
        cancellation: CancellationSignal,
    ) -> SourceEvidence:
        if cancellation.is_cancelled():
            return self._state(source_id, session, "cancelled", started_at)
        if source_id == "system-check":
            return self._system_check(session, cancellation)
        if source_id == "observability":
            return self._observability(session, started_at)
        if source_id == "change-journal":
            return self._change_journal(session, started_at)
        if source_id == "action-center":
            return self._action_center(session, started_at)
        if source_id == "package-health":
            return self._package_health(session, started_at)
        if source_id == "deployment-state":
            return self._deployment_state(session, started_at)
        if source_id == "pending-reboot":
            return self._pending_reboot(session, started_at)
        if source_id == "application-inventory":
            return self._application_inventory(session, started_at)
        if source_id == "network-state":
            return self._network_state(session, started_at)
        if source_id == "dns-state":
            return self._dns_state(session, started_at)
        if source_id == "storage-reclaim":
            return self._storage_reclaim(session, started_at)
        if source_id == "boot-analysis":
            return self._boot_analysis(session, started_at)
        if source_id == "failed-services":
            return self._failed_services(session, started_at)
        if source_id in {"package-history", "deployment-history"}:
            return self._history(source_id, session, started_at)
        return self._state(
            source_id,
            session,
            "unavailable",
            started_at,
            reason_code="collector-unavailable",
            message="This bounded evidence source is unavailable on the current host.",
        )

    def _system_check(
        self,
        session: TroubleshootingSession,
        cancellation: CancellationSignal,
    ) -> SourceEvidence:
        from core.system_check.service import SystemCheckService

        result = SystemCheckService().run(
            cancel_event=cancellation.event,
            persist=True,
        )
        return adapt_system_check(
            result,
            profile_id=session.profile_id,
            variant=session.variant,
        )

    def _observability(
        self,
        session: TroubleshootingSession,
        started_at: float,
    ) -> SourceEvidence:
        from core.observability.timeline import HealthTimelineStore

        store = HealthTimelineStore()
        snapshots = store.load_read_only()
        return adapt_observability(
            snapshots,
            profile_id=session.profile_id,
            variant=session.variant,
            started_at=started_at,
            completed_at=self.clock(),
            last_error=store.last_error,
        )

    def _change_journal(
        self,
        session: TroubleshootingSession,
        started_at: float,
    ) -> SourceEvidence:
        from core.change_journal.service import ChangeJournalService

        snapshot = ChangeJournalService().snapshot(
            limit=100,
            since=max(0.0, started_at - 7 * 24 * 60 * 60),
            refresh=True,
        )
        return adapt_change_journal(
            snapshot,
            profile_id=session.profile_id,
            variant=session.variant,
            started_at=started_at,
            completed_at=self.clock(),
        )

    def _action_center(
        self,
        session: TroubleshootingSession,
        started_at: float,
    ) -> SourceEvidence:
        from core.actions.stores import ActionPlanStore, ActionRunStore

        plans = ActionPlanStore().list_read_only(limit=25)
        runs = ActionRunStore().list_read_only(limit=25)
        return adapt_action_center(
            plans,
            runs,
            profile_id=session.profile_id,
            variant=session.variant,
            started_at=started_at,
            completed_at=self.clock(),
        )

    def _package_health(
        self,
        session: TroubleshootingSession,
        started_at: float,
    ) -> SourceEvidence:
        from services.package.dnf5_health import DNF5HealthService

        report = DNF5HealthService.collect()
        facts = {
            "manager_available": report.package_manager != "Unknown",
            "packagekit_active": report.packagekit_active,
            "locked": report.dnf_locked,
            "repository_ready": report.repo_probe_ok,
            "repository_risk_count": len(report.repo_risks),
        }
        needs_review = (
            not facts["manager_available"]
            or facts["locked"]
            or not facts["repository_ready"]
        )
        findings = (
            self._finding(
                session,
                source_id="package-health",
                finding_type="package-health-degraded",
                category="updates",
                severity="critical" if not facts["repository_ready"] else "attention",
                title="Package health needs review",
                summary="The bounded package-manager checks did not all complete cleanly.",
                evidence=facts,
                resources=("package-manager",),
                next_step=NextStep.navigation(
                    "maintenance:updates",
                    reason_code="review-package-health",
                ),
            ),
        ) if needs_review else ()
        return self._completed("package-health", session, started_at, facts, findings)

    def _deployment_state(
        self,
        session: TroubleshootingSession,
        started_at: float,
    ) -> SourceEvidence:
        pending = bool(SystemManager.has_pending_deployment())
        facts = {"pending_deployment": pending}
        findings = (
            self._finding(
                session,
                source_id="deployment-state",
                finding_type="deployment-pending",
                category="updates",
                severity="attention",
                title="An Atomic deployment is pending",
                summary="A staged deployment is waiting for a reviewed reboot.",
                evidence=facts,
                resources=("rpm-ostree-deployment",),
                next_step=NextStep.manual(
                    "Save your work and review the staged deployment before rebooting.",
                    reason_code="review-pending-deployment",
                ),
            ),
        ) if pending else ()
        return self._completed("deployment-state", session, started_at, facts, findings)

    def _pending_reboot(
        self,
        session: TroubleshootingSession,
        started_at: float,
    ) -> SourceEvidence:
        pending = session.variant == "atomic" and bool(SystemManager.has_pending_deployment())
        facts = {"pending_reboot": pending}
        findings = (
            self._finding(
                session,
                source_id="pending-reboot",
                finding_type="pending-reboot",
                category="deployment",
                severity="attention",
                title="A reboot is needed to continue",
                summary="The current Atomic deployment has staged work waiting for reboot.",
                evidence=facts,
                resources=("rpm-ostree-deployment",),
                next_step=NextStep.manual(
                    "Save your work and review the pending deployment before rebooting.",
                    reason_code="pending-deployment-reboot",
                ),
            ),
        ) if pending else ()
        return self._completed("pending-reboot", session, started_at, facts, findings)

    def _application_inventory(
        self,
        session: TroubleshootingSession,
        started_at: float,
    ) -> SourceEvidence:
        application_id = str(dict(session.profile_parameters).get("application_id", ""))
        available = bool(application_id and shutil.which(application_id))
        facts = {"application_id": application_id, "application_available": available}
        findings = (
            self._finding(
                session,
                source_id="application-inventory",
                finding_type="application-not-found",
                category="applications",
                severity="attention",
                title="The application command was not found",
                summary="The bounded local inventory could not resolve the selected application.",
                evidence=facts,
                resources=(f"application:{application_id}",),
                next_step=NextStep.navigation(
                    "software:apps",
                    {"application_id": application_id},
                    reason_code="review-application-inventory",
                ),
                evidence_quality="limited",
            ),
        ) if not available else ()
        return self._completed("application-inventory", session, started_at, facts, findings)

    def _network_state(
        self,
        session: TroubleshootingSession,
        started_at: float,
    ) -> SourceEvidence:
        from services.network.network import NetworkUtils

        active = bool(NetworkUtils.get_active_connection())
        facts = {"active_connection": active}
        findings = (
            self._finding(
                session,
                source_id="network-state",
                finding_type="network-disconnected",
                category="network",
                severity="attention",
                title="No active network connection was found",
                summary="NetworkManager did not report an active connection.",
                evidence=facts,
                resources=("network-manager",),
                next_step=NextStep.navigation(
                    "network",
                    reason_code="review-network-state",
                ),
            ),
        ) if not active else ()
        return self._completed("network-state", session, started_at, facts, findings)

    def _dns_state(
        self,
        session: TroubleshootingSession,
        started_at: float,
    ) -> SourceEvidence:
        try:
            content = self.resolv_conf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return self._state(
                "dns-state",
                session,
                "unavailable",
                started_at,
                reason_code="dns-metadata-unavailable",
                message="DNS resolver metadata could not be read.",
            )
        server_count = sum(
            1
            for line in content.splitlines()
            if line.strip().startswith("nameserver ")
        )
        facts = {"server_count": server_count}
        findings = (
            self._finding(
                session,
                source_id="dns-state",
                finding_type="dns-server-missing",
                category="network",
                severity="attention",
                title="No DNS resolver was found",
                summary="The resolver metadata contains no nameserver entry.",
                evidence=facts,
                resources=("dns-resolver",),
                next_step=NextStep.navigation(
                    "network:dns",
                    reason_code="review-dns-state",
                ),
            ),
        ) if server_count == 0 else ()
        return self._completed("dns-state", session, started_at, facts, findings)

    def _storage_reclaim(
        self,
        session: TroubleshootingSession,
        started_at: float,
    ) -> SourceEvidence:
        from services.hardware.disk import DiskManager
        from services.storage.reclaim import ReclaimProbeService

        usage = DiskManager.get_disk_usage("/")
        analysis = ReclaimProbeService().analyze()
        known_bytes = [
            int(category.estimated_bytes)
            for category in analysis.categories
            if category.estimated_bytes is not None
        ]
        usage_percent = float(getattr(usage, "percent_used", 0.0) or 0.0)
        facts = {
            "root_usage_percent": usage_percent,
            "known_reclaim_bytes": sum(known_bytes),
            "measured_category_count": len(known_bytes),
        }
        findings = (
            self._finding(
                session,
                source_id="storage-reclaim",
                finding_type="storage-pressure",
                category="storage",
                severity="critical" if usage_percent >= 95.0 else "attention",
                title="Storage pressure needs review",
                summary="The root filesystem is above the bounded review threshold.",
                evidence=facts,
                resources=("filesystem:/",),
                next_step=NextStep.navigation(
                    "maintenance:cleanup",
                    reason_code="review-storage-reclaim",
                ),
            ),
        ) if usage_percent >= 85.0 else ()
        return self._completed("storage-reclaim", session, started_at, facts, findings)

    def _boot_analysis(
        self,
        session: TroubleshootingSession,
        started_at: float,
    ) -> SourceEvidence:
        from utils.boot_analyzer import BootAnalyzer

        stats = BootAnalyzer.get_boot_stats()
        total = float(getattr(stats, "total_time", 0.0) or 0.0)
        facts = {
            "total_seconds": total,
            "kernel_seconds": float(getattr(stats, "kernel_time", 0.0) or 0.0),
            "userspace_seconds": float(getattr(stats, "userspace_time", 0.0) or 0.0),
        }
        findings = (
            self._finding(
                session,
                source_id="boot-analysis",
                finding_type="slow-boot",
                category="boot",
                severity="attention",
                title="Boot time needs review",
                summary="The bounded boot analysis exceeded the review threshold.",
                evidence=facts,
                resources=("systemd-boot",),
                next_step=NextStep.navigation(
                    "diagnostics:watchtower",
                    reason_code="review-boot-analysis",
                ),
            ),
        ) if total >= 60.0 else ()
        return self._completed("boot-analysis", session, started_at, facts, findings)

    def _failed_services(
        self,
        session: TroubleshootingSession,
        started_at: float,
    ) -> SourceEvidence:
        from services.system.services import ServiceManager

        units = tuple(ServiceManager.get_failed_units())
        names = tuple(
            dict.fromkeys(
                str(getattr(unit, "name", "")).strip()
                for unit in units
                if str(getattr(unit, "name", "")).strip()
            )
        )[:8]
        facts = {"failed_service_count": len(units)}
        findings = (
            self._finding(
                session,
                source_id="failed-services",
                finding_type="failed-services",
                category="services",
                severity="attention",
                title="Failed services need review",
                summary="Systemd reports one or more failed services.",
                evidence=facts,
                resources=tuple(f"systemd-unit:{name}" for name in names)
                or ("systemd-units",),
                next_step=NextStep.navigation(
                    "diagnostics:watchtower",
                    reason_code="review-failed-services",
                ),
            ),
        ) if units else ()
        return self._completed("failed-services", session, started_at, facts, findings)

    def _history(
        self,
        source_id: str,
        session: TroubleshootingSession,
        started_at: float,
    ) -> SourceEvidence:
        from core.change_journal.service import ChangeJournalService

        snapshot = ChangeJournalService().snapshot(
            limit=50,
            since=max(0.0, started_at - 7 * 24 * 60 * 60),
            refresh=True,
        )
        expected = "rpm_ostree" if source_id == "deployment-history" else "dnf5"
        count = sum(
            1
            for event in snapshot.events
            if str(getattr(event, "source", "")) == expected
        )
        return self._completed(
            source_id,
            session,
            started_at,
            {"event_count": count},
            (),
        )

    def _completed(
        self,
        source_id: str,
        session: TroubleshootingSession,
        started_at: float,
        facts: dict[str, Any],
        findings: tuple[TroubleshootingFinding, ...],
    ) -> SourceEvidence:
        return adapt_structured_source(
            profile_id=session.profile_id,
            variant=session.variant,
            source_id=source_id,
            state="completed" if findings else "empty",
            started_at=started_at,
            completed_at=self.clock(),
            facts=facts,
            findings=findings,
        )

    def _state(
        self,
        source_id: str,
        session: TroubleshootingSession,
        state: str,
        started_at: float,
        *,
        reason_code: str = "",
        message: str = "",
        completed_at: float | None = None,
    ) -> SourceEvidence:
        return adapt_structured_source(
            profile_id=session.profile_id,
            variant=session.variant,
            source_id=source_id,
            state=state,
            started_at=started_at,
            completed_at=self.clock() if completed_at is None else completed_at,
            reason_code=reason_code,
            message=message,
        )

    def _finding(
        self,
        session: TroubleshootingSession,
        *,
        source_id: str,
        finding_type: str,
        category: str,
        severity: str,
        title: str,
        summary: str,
        evidence: dict[str, Any],
        resources: tuple[str, ...],
        next_step: NextStep,
        evidence_quality: str = "confirmed",
    ) -> TroubleshootingFinding:
        return TroubleshootingFinding.build(
            finding_type=finding_type,
            category=category,
            severity=severity,  # type: ignore[arg-type]
            title=title,
            summary=summary,
            evidence_explanation="This result uses bounded source-owned metadata collected for the selected profile.",
            source_id=source_id,
            collected_at=self.clock(),
            freshness="fresh",
            evidence_quality=evidence_quality,  # type: ignore[arg-type]
            applicable_variants=frozenset({session.variant}),
            affected_resources=resources,
            evidence=evidence,
            next_step=next_step,
        )


class TroubleshootingService:
    """Run exactly one explicit closed profile and retain its terminal result."""

    def __init__(
        self,
        *,
        collector: EvidenceCollector | None = None,
        store: TroubleshootingSessionStore | None = None,
        variant_resolver: VariantResolver | None = None,
        clock: Callable[[], float] = time.time,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.clock = clock
        self.monotonic = monotonic
        self.collector = collector or DefaultEvidenceCollector(clock=clock)
        self.store = store or TroubleshootingSessionStore()
        self.variant_resolver = variant_resolver or (
            lambda: "atomic" if SystemManager.is_atomic() else "traditional"
        )

    def run(
        self,
        profile_id: str,
        *,
        parameters: dict[str, Any] | None = None,
        cancellation: CancellationSignal | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> TroubleshootingRun:
        """Collect only after this explicit method is called."""
        signal = cancellation or CancellationSignal()
        variant = self.variant_resolver()
        created_at = self.clock()
        session = start_session(
            new_session(
                profile_id,
                variant,
                started_at=created_at,
                parameters=parameters,
            ),
            started_at=created_at,
        )
        previous, read_warning = self._previous_session(profile_id, variant)
        profile = require_profile(profile_id)
        budgets = tuple(
            budget
            for budget in profile.source_budgets
            if variant in budget.variants
        )
        evidence: list[SourceEvidence] = []
        started_monotonic = self.monotonic()

        for index, budget in enumerate(budgets):
            if signal.is_cancelled():
                break
            self._emit(
                progress_callback,
                budget.source_id,
                "running",
                index,
                len(budgets),
                started_monotonic,
            )
            evidence.append(
                self._collect_source(
                    budget,
                    session,
                    signal,
                )
            )
            state = evidence[-1].result.state
            self._emit(
                progress_callback,
                budget.source_id,
                state,
                index + 1,
                len(budgets),
                started_monotonic,
            )
            if signal.is_cancelled():
                break

        completed_at = max(
            self.clock(),
            max(
                (bundle.result.completed_at for bundle in evidence),
                default=session.started_at,
            ),
        )
        terminal = compose_session(
            session,
            evidence,
            completed_at=completed_at,
            cancellation_requested=signal.is_cancelled(),
        )
        comparison = (
            compare_sessions(previous, terminal)
            if previous is not None
            else None
        )
        persistence_warning = read_warning
        try:
            self.store.save(terminal)
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.warning("Troubleshooting session was not persisted: %s", exc)
            persistence_warning = persistence_warning or "session-store-unavailable"
        return TroubleshootingRun(
            terminal,
            comparison,
            persistence_warning,
        )

    def _collect_source(
        self,
        budget: SourceBudget,
        session: TroubleshootingSession,
        cancellation: CancellationSignal,
    ) -> SourceEvidence:
        source_started = self.clock()
        executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix=f"troubleshoot-{budget.source_id}",
        )
        future: Future[SourceEvidence] = executor.submit(
            self.collector.collect,
            budget.source_id,
            session,
            started_at=source_started,
            cancellation=cancellation,
        )
        deadline = self.monotonic() + budget.timeout_seconds
        try:
            while not future.done():
                if cancellation.is_cancelled():
                    future.cancel()
                    return adapt_structured_source(
                        profile_id=session.profile_id,
                        variant=session.variant,
                        source_id=budget.source_id,
                        state="cancelled",
                        started_at=source_started,
                        completed_at=self.clock(),
                        reason_code="session-cancelled",
                        message="Collection was cancelled by the user.",
                    )
                if self.monotonic() >= deadline:
                    future.cancel()
                    return adapt_structured_source(
                        profile_id=session.profile_id,
                        variant=session.variant,
                        source_id=budget.source_id,
                        state="timed_out",
                        started_at=source_started,
                        completed_at=max(
                            self.clock(),
                            source_started + budget.timeout_seconds,
                        ),
                        reason_code="source-timeout",
                        message="The source exceeded its bounded timeout.",
                    )
                cancellation.wait(0.01)
            return future.result()
        except Exception as exc:  # noqa: BLE001 - source isolation boundary
            logger.warning(
                "Troubleshooting source %s failed: %s",
                budget.source_id,
                exc,
            )
            return adapt_structured_source(
                profile_id=session.profile_id,
                variant=session.variant,
                source_id=budget.source_id,
                state="failed",
                started_at=source_started,
                completed_at=self.clock(),
                reason_code="source-failed",
                message="The source failed without retaining usable evidence.",
            )
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def _previous_session(
        self,
        profile_id: str,
        variant: SupportedVariant,
    ) -> tuple[TroubleshootingSession | None, str]:
        try:
            snapshot = self.store.read()
        except (OSError, RuntimeError, TypeError, ValueError):
            return None, "session-store-unavailable"
        candidates = tuple(
            session
            for session in snapshot.sessions
            if session.profile_id == profile_id
            and session.variant == variant
            and session.state in {"completed", "partial"}
        )
        return (candidates[0] if candidates else None), snapshot.reason_code

    def _emit(
        self,
        callback: ProgressCallback | None,
        source_id: str,
        state: str,
        completed_sources: int,
        total_sources: int,
        started_monotonic: float,
    ) -> None:
        if callback is None:
            return
        progress = TroubleshootingProgress(
            source_id,
            state,
            completed_sources,
            total_sources,
            max(0.0, self.monotonic() - started_monotonic),
        )
        try:
            callback(progress)
        except (RuntimeError, TypeError, ValueError):
            return
