"""Deterministic composition for v15's core end-to-end workflows."""

from __future__ import annotations

import re
from collections.abc import Callable

from .models import (
    ActionCenterLink,
    ProcessPressure,
    ReclaimAnalysis,
    ReclaimCategory,
    SlowSystemSnapshot,
    SlowSystemSummary,
    WorkflowDefinition,
    WorkflowState,
)

_UNIT_PATTERN = re.compile(r"^[A-Za-z0-9_.@:-]+\.(?:service|socket|mount|timer|target|path)$")

CORE_WORKFLOWS: tuple[WorkflowDefinition, ...] = (
    WorkflowDefinition("update-system", "Update the system", "maintenance:updates", ("updates", "system update")),
    WorkflowDefinition("install-application", "Install an application", "software:apps", ("apps", "software")),
    WorkflowDefinition("diagnose-slow-system", "Diagnose a slow system", "system-monitor:performance", ("performance", "slow computer")),
    WorkflowDefinition("free-disk-space", "Free disk space", "maintenance:cleanup", ("cleanup", "reclaim space")),
    WorkflowDefinition("protect-recover", "Protect or recover the system", "snapshots", ("recovery points", "backups", "repair loofi")),
)

_WORKFLOW_BY_ID = {workflow.id: workflow for workflow in CORE_WORKFLOWS}


def workflow_definition(workflow_id: str) -> WorkflowDefinition | None:
    """Return one canonical workflow definition by stable ID."""
    return _WORKFLOW_BY_ID.get(str(workflow_id))


class SlowSystemService:
    """Collect and summarize bounded, read-only system-pressure evidence."""

    def __init__(self, collector: Callable[[], SlowSystemSnapshot] | None = None):
        self._collector = collector or self._collect_default

    def collect(self) -> SlowSystemSummary:
        return self.summarize(self._collector())

    @staticmethod
    def summarize(snapshot: SlowSystemSnapshot) -> SlowSystemSummary:
        cpu = snapshot.cpu_percent
        memory = snapshot.memory_percent
        storage = snapshot.storage_percent
        io_wait = snapshot.io_wait_percent
        state: WorkflowState
        steps: tuple[str, ...]

        if storage is not None and storage >= 90:
            state, bottleneck = "critical", "Storage pressure"
            explanation = f"The root filesystem is {storage:.0f}% used, which can disrupt updates, logs, and desktop sessions."
            steps = ("Open Cleanup to preview reclaimable space.", "Keep recovery-point deletion separate from ordinary cleanup.")
        elif memory is not None and memory >= 85:
            state, bottleneck = "critical", "Memory pressure"
            explanation = f"Memory use is {memory:.0f}%; the system may be paging or reclaiming memory aggressively."
            steps = ("Review the top memory-using processes.", "Close or restart only applications you recognize.")
        elif io_wait is not None and io_wait >= 20:
            state, bottleneck = "attention", "Storage I/O wait"
            explanation = f"I/O wait is {io_wait:.0f}%, so storage latency is the strongest current signal."
            steps = ("Review disk activity and SMART health.", "Do not tune or delete data before identifying the busy device.")
        elif cpu is not None and cpu >= 85:
            state, bottleneck = "attention", "CPU pressure"
            explanation = f"CPU use is {cpu:.0f}%; one or more active workloads may be limiting responsiveness."
            steps = ("Review the top CPU-using processes.", "Use process controls only after confirming the owner and task.")
        elif snapshot.failed_services:
            state, bottleneck = "attention", "Failed service"
            explanation = f"{len(snapshot.failed_services)} failed service(s) may be contributing to degraded behavior."
            steps = ("Inspect the failed unit and its journal.", "Review a restart through Action Center only when the unit is still failed.")
        elif snapshot.recurring_signals:
            state, bottleneck = "attention", "Recurring health signal"
            explanation = f"{len(snapshot.recurring_signals)} recurring health signal(s) need review."
            steps = ("Open Health & Troubleshooting for the recorded evidence.",)
        elif any(value is not None for value in (cpu, memory, storage, io_wait)):
            state, bottleneck = "good", "No clear bottleneck"
            explanation = "The bounded snapshot does not show sustained CPU, memory, storage, or I/O pressure."
            steps = ("Re-run the snapshot while the slowdown is happening.", "Review Processes for short-lived spikes.")
        else:
            state, bottleneck = "unknown", "Insufficient data"
            explanation = "The read-only snapshot could not collect enough pressure data."
            steps = ("Retry the snapshot and review Health & Troubleshooting if collection still fails.",)

        eligible_unit = next(
            (unit for unit in snapshot.failed_services if _UNIT_PATTERN.fullmatch(unit)),
            None,
        )
        link = (
            ActionCenterLink(
                "maintenance:action-center",
                "restart-failed-service",
                f"Review restart for {eligible_unit}",
                {"service": eligible_unit},
            )
            if eligible_unit
            else None
        )
        return SlowSystemSummary(state, bottleneck, explanation, steps, snapshot, link)

    @staticmethod
    def _collect_default() -> SlowSystemSnapshot:
        """Compose existing trusted collectors without adding a diagnostic engine."""
        from core.diagnostics.daily_maintenance import DailyMaintenanceService
        from core.observability import HealthTimelineStore, MaintenanceTrendAnalyzer
        from services.system import ProcessManager
        from utils.auto_tuner import AutoTuner

        workload = AutoTuner.detect_workload()
        report = DailyMaintenanceService().collect()
        cards = {card.id: card for card in report.cards}
        disk_card = cards.get("disk-usage")
        service_card = cards.get("failed-services")
        storage_percent = _root_usage_percent(
            disk_card.details if disk_card is not None else ""
        )
        failed_services = _failed_service_units(
            service_card.details if service_card is not None else ""
        )
        top = tuple(
            ProcessPressure(item.name, item.pid, item.cpu_percent, item.memory_percent)
            for item in ProcessManager.get_top_by_cpu(5)
        )
        recurring: tuple[str, ...] = ()
        try:
            trend = MaintenanceTrendAnalyzer(HealthTimelineStore().load()[-30:]).analyze()
            recurring = tuple(item.title for item in trend.recurring[:5])
        except (OSError, ValueError, TypeError):
            recurring = ()
        return SlowSystemSnapshot(
            workload.cpu_percent,
            workload.memory_percent,
            storage_percent,
            workload.io_wait,
            top,
            failed_services,
            recurring,
        )


class ReclaimAnalysisService:
    """Convert read-only size probes into safe workflow categories."""

    @staticmethod
    def build(*, atomic: bool, package_cache_bytes: int | None, journal_bytes: int | None) -> ReclaimAnalysis:
        cache_link = None if atomic else ActionCenterLink(
            "maintenance:action-center",
            "dnf-clean-all",
            "Review package cache cleanup",
        )
        categories = (
            ReclaimCategory(
                "package-cache",
                "Package metadata cache",
                package_cache_bytes,
                "low",
                not atomic and bool(package_cache_bytes),
                (
                    "Atomic Fedora keeps this manual-only; review rpm-ostree status and documented guidance."
                    if atomic
                    else "Action Center creates a fresh Traditional Fedora plan and verifies package health afterward."
                ),
                cache_link,
                manual_only=atomic,
            ),
            ReclaimCategory(
                "journal",
                "System journal",
                journal_bytes,
                "medium",
                False,
                "Review retention before vacuuming logs; this remains on its existing confirmed cleanup path.",
                manual_only=True,
            ),
            ReclaimCategory(
                "filesystem-trim",
                "Supported filesystem trim",
                None,
                "low",
                False,
                "Trim is maintenance, not deletion, and reports no reclaim estimate. Action Center verifies discard support first.",
                ActionCenterLink("maintenance:action-center", "fstrim-all", "Review supported filesystem trim"),
            ),
        )
        return ReclaimAnalysis(atomic=atomic, categories=categories)


def _root_usage_percent(details: str) -> float | None:
    percentages = re.findall(r"\b(\d{1,3})%\b", str(details))
    if not percentages:
        return None
    return float(percentages[-1])


def _failed_service_units(details: str) -> tuple[str, ...]:
    units: list[str] = []
    for line in str(details).splitlines():
        for token in line.replace("●", " ").split():
            if _UNIT_PATTERN.fullmatch(token) and token not in units:
                units.append(token)
                break
    return tuple(units[:10])
