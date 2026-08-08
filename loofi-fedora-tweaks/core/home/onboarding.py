"""Versioned, inert and resumable Home onboarding state."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

from core.state.atomic_io import atomic_write_json
from core.state.paths import StatePaths

SCHEMA_ID = "loofi.home-onboarding"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class OnboardingStep:
    id: str
    title: str
    description: str
    action_label: str
    route_id: str = ""


ONBOARDING_STEPS = (
    OnboardingStep(
        "orientation",
        "Welcome to Loofi Fedora Tweaks",
        "Home brings saved system status, the next useful action, and common Fedora tasks together.",
        "Continue",
    ),
    OnboardingStep(
        "check",
        "Checks run only when you choose",
        "System Check is read-only and starts only from an explicit action. Opening Home never starts it.",
        "Open System Check",
        "health",
    ),
    OnboardingStep(
        "review",
        "Review every system change",
        "Action Center shows risk, scope, validation, and rollback information before Run Plan.",
        "Open Action Center",
        "maintenance:action-center",
    ),
)


@dataclass(frozen=True)
class OnboardingState:
    step: int = 0
    dismissed: bool = False
    completed: bool = False

    @property
    def current_step(self) -> OnboardingStep:
        return ONBOARDING_STEPS[min(max(self.step, 0), len(ONBOARDING_STEPS) - 1)]

    @property
    def visible(self) -> bool:
        return not self.dismissed and not self.completed


class OnboardingStore:
    """Small XDG state owner with legacy first-run sentinel compatibility."""

    def __init__(self, path: Path | None = None, legacy_sentinel: Path | None = None) -> None:
        config = StatePaths.from_environment().config
        self.path = path or config / "onboarding.json"
        self.legacy_sentinel = legacy_sentinel or config / "first_run_complete"

    def load(self) -> OnboardingState:
        if self.legacy_sentinel.exists() and not self.path.exists():
            return OnboardingState(completed=True)
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return OnboardingState()
        if not isinstance(payload, dict):
            return OnboardingState()
        if payload.get("schema") != SCHEMA_ID or payload.get("version") != SCHEMA_VERSION:
            return OnboardingState(dismissed=True)
        step = payload.get("step", 0)
        if not isinstance(step, int):
            step = 0
        return OnboardingState(
            step=min(max(step, 0), len(ONBOARDING_STEPS) - 1),
            dismissed=bool(payload.get("dismissed", False)),
            completed=bool(payload.get("completed", False)),
        )

    def advance(self, state: OnboardingState) -> OnboardingState:
        next_step = state.step + 1
        updated = replace(
            state,
            step=min(next_step, len(ONBOARDING_STEPS) - 1),
            completed=next_step >= len(ONBOARDING_STEPS),
            dismissed=False,
        )
        self._save(updated)
        if updated.completed:
            self.legacy_sentinel.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.legacy_sentinel.touch(mode=0o600, exist_ok=True)
        return updated

    def dismiss(self, state: OnboardingState) -> OnboardingState:
        updated = replace(state, dismissed=True)
        self._save(updated)
        return updated

    def resume(self) -> OnboardingState:
        updated = replace(self.load(), dismissed=False, completed=False)
        self._save(updated)
        return updated

    def _save(self, state: OnboardingState) -> None:
        atomic_write_json(
            self.path,
            {
                "schema": SCHEMA_ID,
                "version": SCHEMA_VERSION,
                "step": state.step,
                "dismissed": state.dismissed,
                "completed": state.completed,
            },
            mode=0o600,
            keep_backup=False,
        )
