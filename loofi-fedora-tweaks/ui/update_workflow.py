"""Compact state-driven Update source cards for the v29 utility shell."""

from __future__ import annotations

from typing import Any, cast

from core.tasks import UPDATE_SOURCES, UpdateOverviewState, UpdateSourceState, update_cta
from services.software.update_overview import Source, UpdateOverviewService
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ui.components import Card, InlineNotice, PageScaffold, PrimaryButton, StatusBadge
from ui.components.layout import AdaptiveGrid
from ui.components.actions import QuietButton


class UpdateWorkflowPage(QWidget):
    """Render System, Flatpak, and Firmware as independent source cards."""

    sourceActionRequested = pyqtSignal(str, str)
    diagnosisRequested = pyqtSignal(str, str)
    stopped = pyqtSignal()

    def __init__(
        self,
        *,
        state: UpdateOverviewState | None = None,
        service: UpdateOverviewService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.state = state or UpdateOverviewState()
        self.service = service or UpdateOverviewService()
        self._check_worker: Any | None = None
        self._checking_source: str | None = None
        self._loading_saved = False
        self._cards: dict[str, tuple[Card, StatusBadge, QLabel, PrimaryButton]] = {}
        self.setObjectName("updateWorkflowPage")
        self.setAccessibleName(self.tr("Update Fedora"))
        self.setAccessibleDescription(self.tr("Check and update system, Flatpak, and firmware sources."))
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scaffold = PageScaffold(
            self.tr("Update"),
            self.tr("Review each source independently. Loofi never reboots automatically."),
        )
        root.addWidget(self.scaffold)
        self.state_notice = InlineNotice(
            self.tr("Choose an update source"),
            self.tr("Each source is checked, reviewed, updated, and verified independently."),
            kind="info",
        )
        self.state_notice.setObjectName("updateWorkflowState")
        self.state_notice.hide()
        self.scaffold.add_widget(self.state_notice)
        self.source_grid = AdaptiveGrid(min_column_width=250, column_breakpoints=((820, 3),))
        self.source_grid.setObjectName("updateSourceGrid")
        self.scaffold.add_widget(self.source_grid)
        self._checked_labels: dict[str, QLabel] = {}
        self._check_again_buttons: dict[str, QuietButton] = {}
        self._diagnose_buttons: dict[str, QuietButton] = {}
        for source in UPDATE_SOURCES:
            self._add_source_card(source)
        from ui.upgrade_preparation import UpgradePreparationCard

        self.preparation = UpgradePreparationCard(parent=self)
        self.preparation.stopped.connect(self._notify_stopped)
        self.scaffold.add_widget(self.preparation)
        self.scaffold.content_layout.addStretch()
        self._render_state()

    def _add_source_card(self, source: str) -> None:
        labels = {
            "system": ("System", "Fedora packages or the current Atomic deployment."),
            "flatpak": ("Flatpak", "Applications and runtimes from configured remotes."),
            "firmware": ("Firmware", "Device firmware reported by fwupd."),
        }
        title, description = labels[source]
        card = Card(self.tr(title), self.tr(description))
        card.setObjectName(f"update{source.title()}Card")
        card.setProperty("surfaceRole", "source")
        status = StatusBadge(self.tr("Not checked"), kind="neutral")
        status.setObjectName(f"update{source.title()}Status")
        card.add_widget(status)
        details = QLabel()
        details.setObjectName(f"update{source.title()}Details")
        details.setWordWrap(True)
        card.add_widget(details)
        checked = QLabel()
        checked.setObjectName(f"update{source.title()}CheckedAt")
        checked.setWordWrap(True)
        checked.setProperty("supportingText", True)
        card.add_widget(checked)
        self._checked_labels[source] = checked
        button = PrimaryButton(
            self.tr("Check"),
            description=self.tr("Check this update source"),
        )
        button.setObjectName(f"update{source.title()}Button")
        button.clicked.connect(lambda _checked=False, selected=source: self._request_source(selected))
        card.add_widget(button)
        again = QuietButton(self.tr("Check again"), description=self.tr("Read fresh update candidates without restarting the previous update."))
        again.clicked.connect(lambda _checked=False, selected=source: self.sourceActionRequested.emit(selected, "check"))
        card.add_widget(again)
        self._check_again_buttons[source] = again
        diagnose = QuietButton(self.tr("Diagnose"), description=self.tr("Open read-only Health checks for this source and its recorded run."))
        diagnose.setObjectName(f"update{source.title()}Diagnose")
        diagnose.clicked.connect(lambda _checked=False, selected=source: self.diagnosisRequested.emit(selected, self.state.source(selected).run_id))
        card.add_widget(diagnose)
        self._diagnose_buttons[source] = diagnose
        self.source_grid.add_card(card)
        self._cards[source] = (card, status, details, button)

    def set_state(self, state: UpdateOverviewState) -> None:
        self.state = state
        self._render_state()

    def set_snapshot(self, snapshot: object) -> None:
        """Project one read-only overview snapshot into the compact cards."""
        incoming = UpdateOverviewState.from_snapshot(snapshot)
        for previous in self.state.sources:
            if previous.run_id and (previous.status in {"awaiting_reboot", "verifying", "preparing"}
                                    or previous.source != self._checking_source and previous.metadata.get("recovery_required")):
                incoming = incoming.replace_source(previous)
        self.set_state(incoming)

    def set_loading(self, loading: bool) -> None:
        self._loading_saved = loading
        self._render_state()

    def restore_saved_state(self, state: UpdateOverviewState) -> None:
        self.set_state(state)
        problems = [item for item in state.sources if item.metadata.get("recovery_required")]
        if problems:
            self.set_notice("warning", "Saved update needs review", problems[0].message)
        else:
            self.state_notice.hide()

    def set_source(self, source: UpdateSourceState) -> None:
        self.set_state(self.state.replace_source(source))

    def set_notice(self, kind: str, title: str, message: str) -> None:
        """Show a bounded lifecycle message without adding another CTA."""
        self.state_notice.set_notice(kind, self.tr(title), self.tr(message))
        self.state_notice.show()

    def start_check(self, source: str) -> bool:
        """Run one explicit, read-only source check on a worker thread."""
        source = str(source or "").strip()
        if source not in UPDATE_SOURCES:
            return False
        worker = self._check_worker
        if worker is not None and worker.isRunning():
            return False
        from ui.update_overview import UpdateCheckWorker

        reset_cancel = getattr(self.service, "reset_cancel", None)
        if callable(reset_cancel):
            reset_cancel()
        current = self.source_state(source)
        if self._loading_saved or current.status in {"verifying", "awaiting_reboot", "preparing"}:
            return False
        self.set_source(
            current.with_status(
                "checking",
                stale=True,
                message=self.tr("Reading this source without applying changes."),
                metadata={**current.metadata, "recovery_required": False},
            )
        )
        self.set_notice("info", "Checking", f"Checking {source} updates without changing the system.")
        self._checking_source = source
        worker = UpdateCheckWorker(self.service, sources=(cast(Source, source),))
        worker.sourceCompleted.connect(self._on_check_snapshot)
        worker.completed.connect(self._on_check_snapshot)
        worker.failed.connect(lambda _message, checked=source: self._on_check_failed(checked))
        worker.finished.connect(self._on_check_finished)
        self._check_worker = worker
        worker.start_check()
        return True

    def cancel_check(self) -> bool:
        """Request cooperative cancellation of the active source check."""
        worker = self._check_worker
        if worker is None or not worker.isRunning():
            return False
        self.service.cancel()
        self.set_notice("warning", "Check cancelled", "The previous source result remains visible.")
        return True

    def _on_check_snapshot(self, snapshot: object) -> None:
        self.set_snapshot(snapshot)

    def _on_check_failed(self, source: str) -> None:
        current = self.source_state(source)
        self.set_source(
            current.with_status(
                "error",
                stale=True,
                message=self.tr("The source check failed; refresh before updating."),
            )
        )
        self.set_notice("warning", "Check failed", f"Could not check {source} updates safely.")

    def _on_check_finished(self) -> None:
        self._check_worker = None
        self._checking_source = None
        self._notify_stopped()

    def apply_outcome(self, source: str, outcome: object) -> None:
        """Render a verified controller outcome back into its source card."""
        source = str(source or "").strip()
        if source not in UPDATE_SOURCES:
            return
        current = self.source_state(source)
        status = str(getattr(outcome, "status", "failed"))
        if status in {"succeeded", "completed_verified", "verified"}:
            next_status = "succeeded"
            kind = "success"
            title = "Updated"
        elif status in {"awaiting_reboot", "pending_reboot"}:
            next_status = "awaiting_reboot"
            kind = "warning"
            title = "Reboot required"
        elif status == "verification_failed":
            next_status = "verification_failed"
            kind = "warning"
            title = "Verification failed"
        elif status in {"cancelled", "interrupted"}:
            next_status = "cancelled"
            kind = "warning"
            title = "Update cancelled"
        else:
            next_status = "failed"
            kind = "warning"
            title = "Update failed"
        run_id = str(getattr(outcome, "run_id", "") or "")
        message = str(getattr(outcome, "message", "The update operation finished."))
        self.set_source(
            current.with_status(
                next_status,  # type: ignore[arg-type]
                stale=next_status == "cancelled",
                run_id=run_id or current.run_id,
                reboot_required=next_status == "awaiting_reboot",
                message=message,
                metadata={**current.metadata, "recovery_required": next_status == "verification_failed"},
            )
        )
        self.set_notice(kind, title, message)

    def source_state(self, source: str) -> UpdateSourceState:
        return self.state.source(source)

    def source_button(self, source: str) -> PrimaryButton:
        return self._cards[str(source)][3]

    def focus_task(self, task_id: str) -> bool:
        """Focus one update source card after goal-based search."""
        source = str(task_id or "").strip()
        if source == "update:prepare-upgrade":
            self.preparation.check_button.setFocus()
            return True
        if source.startswith("update:"):
            source = source.removeprefix("update:")
            if source == "overview":
                source = "system"
        card_data = self._cards.get(source)
        if card_data is None:
            self._cards["system"][3].setFocus()
            return False
        button = card_data[3]
        button.setFocus()
        return True

    def _render_state(self) -> None:
        for source in UPDATE_SOURCES:
            state = self.state.source(source)
            _card, badge, details, button = self._cards[source]
            cta = update_cta(state)
            label = {
                "unchecked": "Not checked",
                "checking": "Checking",
                "up_to_date": "No updates",
                "available": "Updates available",
                "stale": "Check required",
                "missing_tool": "Tool missing",
                "unsupported": "Unsupported",
                "error": "Check failed",
                "preparing": "Preparing",
                "verifying": "Verifying",
                "awaiting_reboot": "Reboot required",
                "succeeded": "Updated",
                "cancelled": "Update cancelled",
                "failed": "Update failed",
                "verification_failed": "Verification failed",
            }.get(state.status, state.status)
            kind = "success" if state.status in {"up_to_date", "succeeded"} else "warning" if state.status in {"error", "cancelled", "failed", "verification_failed", "missing_tool", "unsupported"} else "info"
            badge.set_status(self.tr(label), kind=kind)
            if state.status == "unchecked":
                summary = self.tr("Check this source to discover available updates.")
            elif state.status == "up_to_date":
                summary = self.tr("No updates were reported by this source.")
            elif state.status == "awaiting_reboot" or state.reboot_required:
                summary = self.tr("Restart the computer when ready, then continue verification.")
            elif state.status in {"error", "failed", "cancelled", "stale"}:
                summary = self.tr("Check this source again before applying changes.")
            elif state.status == "verification_failed":
                summary = self.tr("Review the failed verification in Activity before another update.")
            elif state.status in {"missing_tool", "unsupported"}:
                summary = self.tr("This source is unavailable on this system.")
            elif state.status == "available":
                summary = self.tr("%1 updates available").replace("%1", str(state.item_count))
                if state.stale:
                    summary += self.tr(" · Check again before updating")
            else:
                summary = ""
            candidate_detail = "\n".join(state.details)
            details.setText("\n".join(part for part in (summary, state.message, candidate_detail) if part))
            checked = self._checked_labels[source]
            checked.setText(self.tr("Last checked: %1").replace("%1", state.checked_at) if state.checked_at else self.tr("Last checked: Never"))
            button.setText(self.tr(cta.label))
            button.setAccessibleName(self.tr(cta.label))
            button.setToolTip(self.tr(cta.reason or cta.label))
            button.setProperty("sourceAction", cta.action)
            button.setProperty("sourceState", state.status)
            button.setEnabled(cta.enabled and not self._loading_saved)
            again = self._check_again_buttons[source]
            again.setVisible(bool(state.run_id) and cta.action == "recovery" and state.status in {"failed", "verification_failed", "cancelled"})
            again.setEnabled(not self._loading_saved)
            diagnose = self._diagnose_buttons[source]
            diagnose.setVisible(state.status in {"error", "failed", "verification_failed", "missing_tool", "unsupported"})
            diagnose.setEnabled(not self._loading_saved)

    @property
    def busy(self) -> bool:
        # Keep the source check owned until its terminal GUI callback arrives.
        return self._check_worker is not None or self.preparation.busy

    def _notify_stopped(self) -> None:
        if not self.busy:
            self.stopped.emit()

    def request_stop(self) -> None:
        self.cancel_check()
        self.preparation.request_stop()

    def cleanup(self, timeout_ms: int = 1000) -> bool:
        """Retain a source worker when it cannot finish within the wait budget."""
        self.request_stop()
        preparation_stopped = self.preparation.cleanup(timeout_ms)
        worker = self._check_worker
        if worker is None:
            return preparation_stopped
        if worker.isRunning() and not worker.wait(timeout_ms):
            return False
        self._check_worker = None
        self._checking_source = None
        self._notify_stopped()
        return preparation_stopped

    def _request_source(self, source: str) -> None:
        cta = update_cta(self.state.source(source))
        if not cta.enabled:
            return
        self.sourceActionRequested.emit(source, cta.action)


UpdateWorkflowWidget = UpdateWorkflowPage
UpdatePage = UpdateWorkflowPage


__all__ = ["UpdatePage", "UpdateWorkflowPage", "UpdateWorkflowWidget"]
