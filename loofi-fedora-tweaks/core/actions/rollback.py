"""Rollback guidance detection for Action Center items."""

from __future__ import annotations

import shutil

from services.system.system import SystemManager

from core.actions.model import ActionRisk, RollbackGuidance


class RollbackGuidanceService:
    """Choose honest rollback guidance without promising recovery guarantees."""

    @classmethod
    def guidance_for(cls, risk_level: ActionRisk, fallback_hint: str = "") -> RollbackGuidance:
        if risk_level not in {"medium", "high"}:
            return RollbackGuidance(
                mechanism="not-required",
                summary=fallback_hint or "No rollback step is required for this low-risk or read-only action.",
                supported=True,
            )

        if SystemManager.is_atomic():
            return RollbackGuidance(
                mechanism="rpm-ostree",
                summary="Atomic Fedora can roll back to the previous deployment with rpm-ostree rollback after a reboot.",
                command_preview=["rpm-ostree", "rollback"],
                supported=True,
            )

        if shutil.which("snapper"):
            return RollbackGuidance(
                mechanism="snapper",
                summary="Snapper is available. Create a pre-change snapshot before running this action.",
                command_preview=["pkexec", "snapper", "create", "--description", "Before Loofi Fedora Tweaks action"],
                supported=True,
            )

        if shutil.which("timeshift"):
            return RollbackGuidance(
                mechanism="timeshift",
                summary="Timeshift is available. Create a manual snapshot before running this action.",
                command_preview=["pkexec", "timeshift", "--create"],
                supported=True,
            )

        return RollbackGuidance(
            mechanism="manual",
            summary=fallback_hint or "No supported snapshot tool was detected. Review the command preview and keep manual recovery notes before continuing.",
            supported=False,
        )
