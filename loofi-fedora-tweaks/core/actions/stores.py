"""Atomic, bounded stores for v14 Action Center plans and runs."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import List, Mapping

from core.actions.contracts import ActionPlan, ActionRun
from core.state.atomic_io import advisory_lock, atomic_write_json, atomic_write_text
from core.state.paths import StatePaths

ACTION_PLAN_SCHEMA_VERSION = 4
ACTION_RUN_SCHEMA_VERSION = 4
MAX_ACTION_PLANS = 50
MAX_ACTION_RUNS = 100


class ActionStoreVersionError(ValueError):
    """Raised rather than overwriting state written by a newer application."""


class ActionPlanStore:
    """Atomic JSON store retaining the newest 50 plans."""

    def __init__(self, path: Path | None = None, *, max_plans: int = MAX_ACTION_PLANS):
        self.path = path or (StatePaths.from_environment().data / "action_plans.json")
        self.max_plans = max(1, max_plans)

    def _load_unlocked(self, *, migrate: bool = True) -> list[ActionPlan]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return []
        if not isinstance(payload, Mapping):
            return []
        version = int(payload.get("schema_version", 0))
        if version not in {1, 2, 3, ACTION_PLAN_SCHEMA_VERSION}:
            raise ActionStoreVersionError(f"Unsupported action plan schema version: {version}")
        raw_plans = payload.get("plans", [])
        if not isinstance(raw_plans, list):
            return []
        plans: list[ActionPlan] = []
        for raw in raw_plans:
            if not isinstance(raw, Mapping):
                continue
            try:
                plans.append(ActionPlan.from_dict(raw))
            except (KeyError, TypeError, ValueError):
                continue
        if migrate and version in {1, 2, 3}:
            self._write_unlocked(plans)
        return plans

    def _write_unlocked(self, plans: list[ActionPlan]) -> None:
        atomic_write_json(
            self.path,
            {
                "schema_version": ACTION_PLAN_SCHEMA_VERSION,
                "plans": [candidate.to_dict() for candidate in plans[-self.max_plans :]],
            },
        )

    def list(self, *, limit: int | None = None) -> list[ActionPlan]:
        with advisory_lock(self.path):
            plans = self._load_unlocked()
        return plans[-limit:] if limit is not None else plans

    def list_read_only(self, *, limit: int | None = None) -> List[ActionPlan]:
        """Read supported plans without migrating or rewriting their store."""
        with advisory_lock(self.path):
            plans = self._load_unlocked(migrate=False)
        return plans[-limit:] if limit is not None else plans

    def get(self, plan_id: str) -> ActionPlan | None:
        return next((plan for plan in reversed(self.list()) if plan.plan_id == plan_id), None)

    def save(self, plan: ActionPlan) -> None:
        with advisory_lock(self.path):
            plans = [candidate for candidate in self._load_unlocked() if candidate.plan_id != plan.plan_id]
            plans.append(plan)
            self._write_unlocked(plans)


class ActionRunStore:
    """Atomic JSONL store retaining the newest 100 run records."""

    def __init__(self, path: Path | None = None, *, max_runs: int = MAX_ACTION_RUNS):
        self.path = path or (StatePaths.from_environment().data / "action_runs.jsonl")
        self.max_runs = max(1, max_runs)

    def _load_unlocked(self, *, migrate: bool = True) -> list[ActionRun]:
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        runs: list[ActionRun] = []
        migration_required = False
        for line in lines:
            try:
                raw = json.loads(line)
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(raw, Mapping):
                continue
            version = int(raw.get("action_run_schema_version", 0))
            if version not in {1, 2, 3, ACTION_RUN_SCHEMA_VERSION}:
                raise ActionStoreVersionError(f"Unsupported action run schema version: {version}")
            migration_required = migration_required or version in {1, 2, 3}
            try:
                runs.append(ActionRun.from_dict(raw))
            except (KeyError, TypeError, ValueError):
                continue
        if migrate and migration_required:
            self._write_unlocked(runs)
        return runs

    def _write_unlocked(self, runs: list[ActionRun]) -> None:
        records = []
        for run in runs[-self.max_runs :]:
            records.append(json.dumps({"action_run_schema_version": ACTION_RUN_SCHEMA_VERSION, **run.to_dict()}, sort_keys=True, default=str))
        atomic_write_text(self.path, ("\n".join(records) + "\n") if records else "")

    def list(self, *, limit: int | None = None) -> list[ActionRun]:
        with advisory_lock(self.path):
            runs = self._load_unlocked()
        return runs[-limit:] if limit is not None else runs

    def list_read_only(self, *, limit: int | None = None) -> List[ActionRun]:
        """Read supported runs without migrating or rewriting their store."""
        with advisory_lock(self.path):
            runs = self._load_unlocked(migrate=False)
        return runs[-limit:] if limit is not None else runs

    def get(self, run_id: str) -> ActionRun | None:
        return next((run for run in reversed(self.list()) if run.run_id == run_id), None)

    def save(self, run: ActionRun) -> None:
        with advisory_lock(self.path):
            runs = [candidate for candidate in self._load_unlocked() if candidate.run_id != run.run_id]
            runs.append(run)
            self._write_unlocked(runs)

    def interrupt_incomplete(self, *, now: float | None = None) -> List[ActionRun]:
        """Mark stale non-terminal work interrupted; never retry or roll it back."""
        timestamp = time.time() if now is None else now
        interrupted: List[ActionRun] = []
        with advisory_lock(self.path):
            runs = self._load_unlocked()
            for run in runs:
                # Only execution-in-progress is abandoned on restart.  A
                # persisted ``verifying`` state is the deliberate hand-off
                # between ``apply`` and the separate CLI/GUI verify step.
                if run.state == "running":
                    run.transition("interrupted", "application-restart", at=timestamp)
                    run.recovery_status = "manual-review-required"
                    interrupted.append(run)
            if interrupted:
                self._write_unlocked(runs)
        return interrupted
