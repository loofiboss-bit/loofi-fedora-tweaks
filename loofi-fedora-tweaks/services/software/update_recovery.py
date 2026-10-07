"""Restore update presentation from observations and durable runs, never execute."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import math
from typing import get_args

from core.actions.contracts import RunState
from core.actions.stores import ActionPlanStore, ActionRunStore
from core.tasks.update_flow import UPDATE_ACTION_SOURCES, UPDATE_SOURCES, UpdateOverviewState
from services.software.update_overview import UpdateOverviewService


class UpdateRecoveryService:
    """Read-only hydration; only persisted pending runs can offer verification."""

    def __init__(self, overview=None, run_store=None, plan_store=None):
        self.overview = overview if overview is not None else UpdateOverviewService()
        self.run_store = run_store if run_store is not None else ActionRunStore()
        self.plan_store = plan_store if plan_store is not None else ActionPlanStore()

    def load(self) -> UpdateOverviewState:
        snapshot = self.overview.load()
        state = UpdateOverviewState.from_snapshot(snapshot)
        storage_status = str(getattr(snapshot, "storage_status", "ok"))
        if storage_status not in {"ok", "missing", "legacy_schema"}:
            state = UpdateOverviewState(tuple(replace(
                item, status="error", stale=True,
                message="Saved update observations could not be read. Check this source again.",
            ) for item in state.sources))
        try:
            runs = self.run_store.list_read_only(strict=True)
            plans = {plan.plan_id: plan for plan in self.plan_store.list_read_only()}
            for run in runs:
                if run.state not in get_args(RunState) or not math.isfinite(run.updated_at) or run.updated_at < 0:
                    raise ValueError("Saved action history has an invalid state or timestamp.")
                datetime.fromtimestamp(run.updated_at, timezone.utc)
                for result in (run.verification_result, run.execution_result):
                    if result is not None and not isinstance(result, dict):
                        raise ValueError("Saved action history has an invalid result.")
        except (OSError, OverflowError, ValueError, TypeError, KeyError):
            return UpdateOverviewState(tuple(replace(
                item, status="error", stale=True, run_id="", reboot_required=False,
                message="Saved action history is unreadable. Review Activity before updating.",
                metadata={**item.metadata, "recovery_required": True},
            ) for item in state.sources))

        for source in UPDATE_SOURCES:
            candidates = [run for run in runs if UPDATE_ACTION_SOURCES.get(run.action_id) == source]
            if not candidates:
                continue
            pending = [run for run in candidates if run.state in {"running", "verifying", "awaiting_reboot"}]
            run = max(pending or candidates, key=lambda item: item.updated_at)
            current = state.source(source)
            # A newer deliberate source check supersedes an old terminal result,
            # but never a pending run that still requires its own verification.
            if not pending and current.checked_at:
                try:
                    checked = datetime.fromisoformat(current.checked_at.replace("Z", "+00:00")).timestamp()
                except (ValueError, OverflowError):
                    checked = 0.0
                if checked > run.updated_at:
                    continue
            status = run.state if run.state in {"verifying", "awaiting_reboot", "succeeded", "failed", "verification_failed", "cancelled"} else "failed"
            recovery = run.state in {"running", "interrupted", "verification_failed"}
            plan = plans.get(run.plan_id)
            if pending and (plan is None or plan.action_id != run.action_id):
                status, recovery = "error", True
                message = "The saved update plan is unavailable. Review Activity; no update was restarted."
            elif recovery:
                message = "This update needs review in Activity. No update was restarted."
            else:
                result = run.verification_result or run.execution_result or {}
                message = str(result.get("message", "")) or "Saved update result restored. No update was restarted."
            state = state.replace_source(replace(
                current, status=status,  # type: ignore[arg-type]
                run_id=run.run_id, stale=status not in {"verifying", "awaiting_reboot", "succeeded"},
                reboot_required=status == "awaiting_reboot", message=message,
                checked_at=current.checked_at or datetime.fromtimestamp(run.updated_at, timezone.utc).isoformat(),
                metadata={**current.metadata, "recovery_required": recovery, "saved_run_state": run.state},
            ))
        return state
