"""Trusted Change Journal and conservative recovery handoff."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.change_journal.models import ChangeEvent, ChangeJournalSnapshot
from core.plugins.interface import PluginInterface
from core.plugins.metadata import PluginMetadata
from core.product_catalog import plugin_metadata_for_module
from core.workers import BaseWorker
from ui.components import (
    ActionBar,
    Card,
    DefinitionList,
    EmptyState,
    InlineNotice,
    PageScaffold,
    PrimaryButton,
    SecondaryButton,
    StatusBadge,
)


class _JournalService(Protocol):
    def snapshot(self, *, limit: int = 100, refresh: bool = False) -> ChangeJournalSnapshot:
        ...


class ActivityJournalWorker(BaseWorker):
    """Collect trusted local history away from the UI thread."""

    def __init__(self, service: _JournalService, *, refresh: bool, parent=None) -> None:
        super().__init__(parent)
        self.service = service
        self.refresh_sources = refresh

    def do_work(self) -> ChangeJournalSnapshot:
        self.report_progress(self.tr("Reading trusted local sources…"), 30)
        result = self.service.snapshot(limit=100, refresh=self.refresh_sources)
        self.report_progress(self.tr("Preparing activity history…"), 90)
        return result


class ActivityRecoveryTab(QWidget, PluginInterface):
    """Explicitly loaded activity ledger with inert recovery metadata."""

    actionCenterRequested = pyqtSignal(str, object)
    _METADATA = plugin_metadata_for_module(__name__)
    _SOURCE_LABELS = {
        "action_center": "Action Center",
        "dnf5": "DNF5",
        "rpm_ostree": "rpm-ostree",
        "flatpak": "Flatpak",
        "fwupd": "Firmware",
        "loofi_app": "Loofi",
        "session": "Session",
    }

    def __init__(self, *, journal_service: _JournalService | None = None) -> None:
        super().__init__()
        if journal_service is None:
            from core.change_journal import ChangeJournalService

            journal_service = ChangeJournalService()
        self.journal_service = journal_service
        self._snapshot: ChangeJournalSnapshot | None = None
        self._events_by_id: dict[str, ChangeEvent] = {}
        self._worker: ActivityJournalWorker | None = None
        self._setup_ui()

    def metadata(self) -> PluginMetadata:
        return self._METADATA

    def create_widget(self) -> QWidget:
        return self

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scaffold = PageScaffold(
            self.tr("Activity & Recovery"),
            self.tr("Review trusted local change history and prepare only supported recovery actions."),
        )
        root.addWidget(self.scaffold)

        notice = InlineNotice(
            self.tr("History is evidence, not an undo script"),
            self.tr(
                "Loofi reads local records only when you ask. Recovery is offered only when "
                "the current system state can be checked again in Action Center."
            ),
            kind="info",
        )
        notice.setObjectName("activityTrustNotice")
        self.scaffold.add_widget(notice)

        actions = ActionBar()
        self.load_button = PrimaryButton(
            self.tr("Load activity"),
            description=self.tr("Read the latest records from supported local sources."),
        )
        self.load_button.setObjectName("activityLoadButton")
        self.load_button.clicked.connect(lambda: self.load_activity(refresh=False))
        self.refresh_button = SecondaryButton(
            self.tr("Refresh sources"),
            description=self.tr("Discard the short-lived cache and reread local sources."),
        )
        self.refresh_button.setObjectName("activityRefreshButton")
        self.refresh_button.clicked.connect(lambda: self.load_activity(refresh=True))
        self.refresh_button.setEnabled(False)
        actions.add_action(self.refresh_button)
        actions.add_action(self.load_button, primary=True)
        self.scaffold.add_widget(actions)

        self.feedback = QLabel(self.tr("Activity has not been loaded."))
        self.feedback.setObjectName("activityFeedback")
        self.feedback.setWordWrap(True)
        self.feedback.setAccessibleName(self.tr("Activity loading status"))
        self.scaffold.add_widget(self.feedback)

        self.table = QTableWidget(0, 4)
        self.table.setObjectName("activityTable")
        self.table.setHorizontalHeaderLabels(
            [self.tr("When"), self.tr("Change"), self.tr("Source"), self.tr("State")]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(False)
        vertical_header = self.table.verticalHeader()
        if vertical_header is not None:
            vertical_header.hide()
        header = self.table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._render_selected)
        self.table.hide()
        self.scaffold.add_widget(self.table, 1)

        self.empty_state = EmptyState(
            self.tr("No activity loaded"),
            self.tr("Choose Load activity to read supported local history."),
        )
        self.empty_state.setObjectName("activityEmptyState")
        self.scaffold.add_widget(self.empty_state)

        self.detail_card = Card(
            self.tr("Change details"),
            self.tr("Select a row to inspect its recorded facts and recovery status."),
        )
        self.detail_card.setObjectName("activityDetailCard")
        self.detail_status = StatusBadge(self.tr("No change selected"), kind="neutral")
        self.detail_status.setObjectName("activityRecoveryStatus")
        self.detail_definitions = DefinitionList()
        self.related_label = QLabel()
        self.related_label.setObjectName("activityRelated")
        self.related_label.setWordWrap(True)
        self.recovery_guidance = QLabel()
        self.recovery_guidance.setObjectName("activityRecoveryGuidance")
        self.recovery_guidance.setWordWrap(True)
        self.review_button = PrimaryButton(
            self.tr("Review recovery in Action Center"),
            description=self.tr("Open a fresh recovery review. This does not apply a change."),
        )
        self.review_button.setObjectName("activityReviewRecovery")
        self.review_button.clicked.connect(self._review_recovery)
        self.review_button.hide()
        self.detail_card.add_widget(self.detail_status)
        self.detail_card.add_widget(self.detail_definitions)
        self.detail_card.add_widget(self.related_label)
        self.detail_card.add_widget(self.recovery_guidance)
        self.detail_card.add_widget(self.review_button)
        self.scaffold.add_widget(self.detail_card)

    def load_activity(self, *, refresh: bool) -> None:
        """Start one explicit, non-overlapping local collection."""
        if self._worker is not None and self._worker.isRunning():
            return
        self.load_button.set_loading(True, self.tr("Loading activity…"))
        self.refresh_button.setEnabled(False)
        self.feedback.setText(self.tr("Reading supported local sources…"))
        worker = ActivityJournalWorker(self.journal_service, refresh=refresh, parent=self)
        worker.finished.connect(self._loaded)
        worker.error.connect(self._load_failed)
        worker.finished.connect(worker.deleteLater)
        worker.error.connect(worker.deleteLater)
        self._worker = worker
        worker.start()

    def _loaded(self, result: object) -> None:
        if not isinstance(result, ChangeJournalSnapshot):
            self._load_failed(self.tr("The activity source returned an invalid result."))
            return
        self._snapshot = result
        self._events_by_id = {event.event_id: event for event in result.events}
        self.load_button.reset_state()
        self.load_button.setText(self.tr("Load again"))
        self.refresh_button.setEnabled(True)
        self._render_sources(result)
        self._render_events(result.events)
        self._worker = None

    def _load_failed(self, message: str) -> None:
        self.load_button.reset_state()
        self.refresh_button.setEnabled(self._snapshot is not None)
        self.feedback.setText(
            self.tr("Activity could not be loaded: %1").replace("%1", str(message))
        )
        self._worker = None

    def _render_sources(self, snapshot: ChangeJournalSnapshot) -> None:
        available = sum(source.availability == "available" for source in snapshot.sources)
        partial = sum(source.availability == "partial" for source in snapshot.sources)
        unavailable = sum(source.availability == "unavailable" for source in snapshot.sources)
        message = self.tr("%1 source(s) ready · %2 partial · %3 unavailable").replace(
            "%1", str(available)
        ).replace("%2", str(partial)).replace("%3", str(unavailable))
        if snapshot.truncated:
            message += self.tr(" · Showing the newest 100 changes")
        self.feedback.setText(message)

    def _render_events(self, events: tuple[ChangeEvent, ...]) -> None:
        self.table.setRowCount(0)
        if not events:
            self.table.hide()
            self.empty_state.title_label.setText(self.tr("No recorded changes"))
            self.empty_state.set_message(
                self.tr("The available sources did not report any changes.")
            )
            self.empty_state.show()
            return
        self.empty_state.hide()
        self.table.show()
        for event in events:
            row = self.table.rowCount()
            self.table.insertRow(row)
            when = datetime.fromtimestamp(event.occurred_at).astimezone().strftime("%Y-%m-%d %H:%M")
            values = (
                when,
                event.summary,
                self._SOURCE_LABELS.get(event.source, event.source),
                event.state.replace("_", " ").title(),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, event.event_id)
                item.setToolTip(value)
                self.table.setItem(row, column, item)
        self.table.selectRow(0)

    def _selected_event(self) -> ChangeEvent | None:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        event_id = str(item.data(Qt.ItemDataRole.UserRole)) if item is not None else ""
        return self._events_by_id.get(event_id)

    def _render_selected(self) -> None:
        event = self._selected_event()
        if event is None:
            return
        self.detail_card.set_heading(event.summary, self.tr("Recorded by %1").replace(
            "%1", self._SOURCE_LABELS.get(event.source, event.source)
        ))
        for row in self.detail_definitions.rows:
            self.detail_definitions.body.removeWidget(row)
            row.deleteLater()
        self.detail_definitions.rows.clear()
        self.detail_definitions.add_row(
            self.tr("State"), event.state.replace("_", " ").title()
        )
        self.detail_definitions.add_row(
            self.tr("Resources"),
            ", ".join(event.resources) or self.tr("Not recorded"),
        )
        self.detail_definitions.add_row(
            self.tr("Reboot"),
            self.tr("Required") if event.reboot_required else self.tr("Not required"),
        )
        related = len(event.correlation_ids)
        self.related_label.setText(
            self.tr("Possibly related: %1 change(s). This is a time-and-resource match, not proof of cause.")
            .replace("%1", str(related))
        )
        recovery = event.recovery
        self.review_button.hide()
        if recovery.kind == "action_center":
            self.detail_status.set_status(
                self.tr("Recovery can be reviewed"),
                kind="warning",
                description=self.tr("Current state will be checked again before a plan is created."),
            )
            self.recovery_guidance.setText(
                recovery.guidance or self.tr("Review this recovery in Action Center.")
            )
            self.review_button.show()
        elif recovery.kind == "manual_guidance":
            self.detail_status.set_status(self.tr("Manual recovery guidance"), kind="neutral")
            self.recovery_guidance.setText(recovery.guidance)
        else:
            self.detail_status.set_status(self.tr("No supported recovery"), kind="neutral")
            self.recovery_guidance.setText(
                recovery.guidance or self.tr("This record is available for review only.")
            )

    def _review_recovery(self) -> None:
        event = self._selected_event()
        if event is None or event.recovery.kind != "action_center":
            return
        self.actionCenterRequested.emit(
            str(event.recovery.action_id),
            dict(event.recovery.parameters),
        )
