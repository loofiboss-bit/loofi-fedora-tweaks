"""History projections for the Changes/Action Center view."""

from __future__ import annotations

import typing

from ui.action_center_presentation import (
    filter_lifecycle_records,
    format_history_records,
)


class ActionCenterHistoryMixin:
    """Keep persisted-history presentation separate from lifecycle controls."""

    def _show_recent_changes(self: typing.Any) -> None:
        """Show persisted outcomes in one compact, user-facing history view."""
        from core.actions import ActionPlanStore, ActionRunStore

        try:
            plans = ActionPlanStore().list(limit=25)
            runs = ActionRunStore().list(limit=25)
        except (OSError, RuntimeError, TypeError, ValueError):
            plans = []
            runs = []

        records: list[tuple[str, typing.Any]] = []
        for group_id in ("completed", "waiting_restart", "failed"):
            records.extend(
                filter_lifecycle_records(
                    group_id,
                    plans,
                    runs,
                    "",
                    self._items,
                    self._ACTION_ID_ADAPTERS,
                )
            )

        def _record_timestamp(record: typing.Any) -> float:
            for field in ("updated_at", "created_at"):
                try:
                    return float(getattr(record, field, 0.0) or 0.0)
                except (TypeError, ValueError):
                    continue
            return 0.0

        seen: set[str] = set()
        unique: list[tuple[str, typing.Any]] = []
        for kind, record in sorted(
            records,
            key=lambda pair: _record_timestamp(pair[1]),
            reverse=True,
        ):
            record_id = str(
                getattr(record, "run_id", "")
                or getattr(record, "plan_id", "")
                or ""
            )
            if not record_id or record_id in seen:
                continue
            seen.add(record_id)
            unique.append((kind, record))

        self.mode_switcher.set_active_view("queue")
        self.master_pane.lifecycle_controls.hide()
        self._current_plan = None
        self._current_run = None
        self._visible_records = unique
        self.action_list.clear()
        for kind, record in self._visible_records:
            self.master_pane.add_record(kind, record, self._action_title)
        self._set_lifecycle_primary("", enabled=False)
        if self._visible_records:
            self.presentation_banner.set_result(
                "info",
                self.tr("Recent changes"),
                self.tr("%1 saved change(s) are shown newest first. Select one to inspect its result.")
                .replace("%1", str(len(self._visible_records))),
            )
            self.action_list.setCurrentRow(0)
        else:
            self.presentation_banner.set_result(
                "success",
                self.tr("No recent changes"),
                self.tr("No completed or in-progress changes have been recorded yet."),
            )
            self.selected_summary.setText(self.tr("No recent changes have been recorded."))
            self.detail_area.setPlainText(self.tr("Run a reviewed change to see its outcome here."))

    def _show_history(self: typing.Any) -> None:
        """Show the compact Action Center history and preserve reviewability."""
        from core.actions import ActionPlanStore, ActionRunStore

        history = self._service.recent_history(limit=25)
        plans = ActionPlanStore().list(limit=25)
        runs = ActionRunStore().list(limit=25)
        if not history and not plans and not runs:
            self.selected_summary.setText(
                self.tr("No Action Center history has been recorded.")
            )
            self.detail_area.setPlainText(self.tr("No Action Center history recorded."))
            return
        lines = format_history_records(plans, runs, history)
        self.selected_summary.setText(
            self.tr("Loaded %d recent Action Center records.") % len(lines)
        )
        self.detail_area.setPlainText("\n".join(lines))
        viable = next(
            (
                plan
                for plan in reversed(plans)
                if plan.state in {"ready", "needs_review"} and not plan.is_expired()
            ),
            None,
        )
        if viable is not None:
            self._current_plan = viable
            self._set_lifecycle_primary("run", enabled=True)
