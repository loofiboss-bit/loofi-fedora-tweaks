"""Focused review copy for verified tweak changes and restorations."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from ui.confirm_dialog import ReviewedActionDialog


def system_tweak_review(
    parent: Any,
    tweak: Any,
    current_value: str,
    selected_value: str,
    translate: Callable[[str], object],
) -> ReviewedActionDialog:
    def t(value: str) -> str:
        return str(translate(value))

    labels = dict(tweak.choices)
    scope = "\n".join((
        f"{t('Setting')}: {t(tweak.title)}",
        f"{t('Current')}: {t(labels.get(current_value, current_value or t('Unknown')))}",
        f"{t('Selected')}: {t(labels.get(selected_value, selected_value))}",
        t("Scope: this computer, all users."),
    ))
    return ReviewedActionDialog(
        t("Change system setting: %1").replace("%1", t(tweak.title)),
        t("Apply this exact setting value and verify it before reporting success."),
        scope,
        t("Automatic rollback is unavailable. After a verified change, Tweaks can offer the recorded previous value for a separate verified restore."),
        require_no_rollback_acceptance=True,
        parent=parent,
    )


def tweak_restore_review(
    parent: Any,
    tweak: Any,
    facts: Mapping[str, object],
    recovery_guidance: str,
    translate: Callable[[str], object],
) -> ReviewedActionDialog:
    def t(value: str) -> str:
        return str(translate(value))

    scope = "\n".join((
        f"{t('Current')}: {facts['current']}",
        f"{t('Previous verified value')}: {facts['requested']}",
        t("Scope: this computer, all users.") if tweak.system_wide else t("Scope: this user."),
    ))
    return ReviewedActionDialog(
        t("Restore previous value: %1").replace("%1", t(tweak.title)),
        t("Restore the recorded value and verify the result."),
        scope,
        recovery_guidance,
        require_no_rollback_acceptance=bool(tweak.system_wide),
        parent=parent,
    )
