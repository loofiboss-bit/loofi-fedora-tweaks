"""Trusted Change Journal and conservative recovery handoff."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from PyQt6.QtCore import QThread, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.change_journal.models import ChangeEvent, ChangeJournalSnapshot, ChangeSource
from core.change_journal.presentation import (
    ActivityPresentationState,
    error_state,
    initial_state,
    loading_state,
    selected_state,
    snapshot_state,
)
from core.plugins.interface import PluginInterface
from core.plugins.metadata import PluginMetadata
from core.product_catalog import plugin_metadata_for_module
from core.workers import BaseWorker
from ui.components import (
    Card,
    DefinitionList,
    DetailsDisclosure,
    EmptyState,
    InlineNotice,
    PageScaffold,
    PrimaryButton,
    SecondaryButton,
    StatusBadge,
)


class _JournalService(Protocol):
    def snapshot(
        self,
        *,
        limit: int = 100,
        since: float | None = None,
        until: float | None = None,
        sources: Iterable[ChangeSource] | None = None,
        statuses: Iterable[str] | None = None,
        reboot_required: bool | None = None,
        search: str | None = None,
        cursor: str | None = None,
        refresh: bool = False,
    ) -> ChangeJournalSnapshot:
        ...

    def export_event(self, event_id: str, *, format: str = "json", refresh: bool = False) -> str:
        ...


class ActivityJournalWorker(BaseWorker):
    """Collect trusted local history away from the UI thread."""

    def __init__(self, service: _JournalService, *, refresh: bool, filters: dict[str, Any], cursor: str | None = None, target_run_id: str = "", parent=None) -> None:
        super().__init__(parent)
        self.service = service
        self.refresh_sources = refresh
        self.filters: dict[str, Any] = dict(filters)
        self.cursor = cursor
        self.target_run_id = str(target_run_id or "")[:128]

    def do_work(self) -> ChangeJournalSnapshot:
        self.report_progress(self.tr("Reading trusted local sources…"), 30)
        direct_lookup = getattr(self.service, "get_run_event", None)
        if self.target_run_id and callable(direct_lookup):
            event = direct_lookup(self.target_run_id)
            result = ChangeJournalSnapshot(
                events=(event,) if event is not None else (),
                sources=(),
                generated_at=0.0,
                truncated=False,
                next_cursor=None,
            )
            self.report_progress(self.tr("Preparing activity history…"), 90)
            return result
        result = self.service.snapshot(
            limit=500 if self.target_run_id else 25,
            cursor=self.cursor,
            refresh=self.refresh_sources,
            **self.filters,
        )
        if self.target_run_id:
            matching = tuple(
                event for event in result.events
                if str(event.after_facts.get("run_id", "")) == self.target_run_id
            )
            result = ChangeJournalSnapshot(
                events=matching,
                sources=result.sources,
                generated_at=result.generated_at,
                truncated=False,
                schema=result.schema,
                next_cursor=None,
            )
        self.report_progress(self.tr("Preparing activity history…"), 90)
        return result


# Parentless workers must survive page destruction until QThread really exits.
# BaseWorker.finished carries a result and is not QThread.finished().
_ACTIVE_JOURNAL_WORKERS: set[ActivityJournalWorker] = set()


def _stop_journal_workers(workers: set[ActivityJournalWorker]) -> None:
    for worker in tuple(workers):
        worker.cancel()
        worker.requestInterruption()
        worker.wait(100)


def _journal_thread_finished(worker: ActivityJournalWorker, workers: set[ActivityJournalWorker]) -> None:
    workers.discard(worker)
    _ACTIVE_JOURNAL_WORKERS.discard(worker)
    worker.deleteLater()


class ActivityRecoveryTab(QWidget, PluginInterface):
    """Explicitly loaded activity ledger with inert recovery metadata."""

    actionCenterRequested = pyqtSignal(str, object)
    _METADATA = plugin_metadata_for_module(__name__)
    _SOURCE_LABELS = {
        "local_loofi": "Local Loofi",
        "action_center": "Change journal",
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
        assert journal_service is not None
        self.journal_service: _JournalService = journal_service
        self._snapshot: ChangeJournalSnapshot | None = None
        self._events_by_id: dict[str, ChangeEvent] = {}
        self._worker: ActivityJournalWorker | None = None
        self._workers: set[ActivityJournalWorker] = set()
        self._closing = False
        workers = self._workers
        self.destroyed.connect(lambda: _stop_journal_workers(workers))
        self._next_cursor: str | None = None
        self._page_filter_key: tuple[tuple[str, Any], ...] | None = None
        self._requested_run_id = ""
        self._initial_load_started = False
        self.presentation_state = initial_state()
        self._setup_ui()
        self._apply_presentation_state(self.presentation_state)

    def metadata(self) -> PluginMetadata:
        return self._METADATA

    def create_widget(self) -> QWidget:
        return self

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scaffold = PageScaffold(
            self.tr("Activity"),
            self.tr("Review trusted local change history and prepare only supported recovery actions."),
        )
        root.addWidget(self.scaffold)

        notice = InlineNotice(
            self.tr("Verified recovery"),
            self.tr(
                "Recent local activity loads automatically. Loofi checks the current "
                "state again before you review a recovery action."
            ),
            kind="info",
        )
        notice.setObjectName("activityTrustNotice")
        self.scaffold.add_widget(notice)

        filter_row = QGridLayout()
        self.activity_view_filter = QComboBox()
        self.activity_view_filter.setObjectName("activityViewFilter")
        self.activity_view_filter.setAccessibleName(self.tr("Activity view"))
        self.activity_view_filter.addItem(self.tr("Needs you"), "needs_you")
        self.activity_view_filter.addItem(self.tr("In progress"), "in_progress")
        self.activity_view_filter.addItem(self.tr("History"), "history")
        filter_row.addWidget(self.activity_view_filter, 0, 0)
        self.source_filter = QComboBox()
        self.source_filter.setObjectName("activitySourceFilter")
        self.source_filter.addItem(self.tr("All sources"), "")
        for source_id, label in self._SOURCE_LABELS.items():
            self.source_filter.addItem(self.tr(label), source_id)
        self.status_filter = QComboBox()
        self.status_filter.setObjectName("activityStatusFilter")
        self.status_filter.addItem(self.tr("All states"), "")
        for state in ("running", "verifying", "awaiting_reboot", "succeeded", "failed", "verification_failed", "cancelled", "interrupted", "recorded"):
            self.status_filter.addItem(self.tr(state.replace("_", " ").title()), state)
        self.reboot_filter = QComboBox()
        self.reboot_filter.setObjectName("activityRebootFilter")
        self.reboot_filter.addItem(self.tr("Any reboot state"), "")
        self.reboot_filter.addItem(self.tr("Reboot required"), "required")
        self.reboot_filter.addItem(self.tr("No reboot recorded"), "not-required")
        self.search_input = QLineEdit()
        self.search_input.setObjectName("activitySearch")
        self.search_input.setPlaceholderText(self.tr("Search action, package, resource…"))
        self.search_input.setAccessibleName(self.tr("Activity search"))
        self.since_input = QLineEdit()
        self.since_input.setObjectName("activitySinceFilter")
        self.since_input.setPlaceholderText(self.tr("Since date (YYYY-MM-DD)"))
        self.until_input = QLineEdit()
        self.until_input.setObjectName("activityUntilFilter")
        self.until_input.setPlaceholderText(self.tr("Until date (YYYY-MM-DD)"))
        filter_row.addWidget(self.search_input, 0, 1, 1, 2)
        self.activity_view_filter.currentIndexChanged.connect(self._filters_changed)
        self.source_filter.currentIndexChanged.connect(self._filters_changed)
        self.status_filter.currentIndexChanged.connect(self._filters_changed)
        self.reboot_filter.currentIndexChanged.connect(self._filters_changed)
        self.search_input.textChanged.connect(self._filters_changed)
        self.since_input.textChanged.connect(self._filters_changed)
        self.until_input.textChanged.connect(self._filters_changed)
        self.scaffold.add_layout(filter_row)
        advanced_content = QWidget(self)
        advanced_layout = QGridLayout(advanced_content)
        for index, widget in enumerate((self.source_filter, self.status_filter, self.reboot_filter, self.since_input, self.until_input)):
            advanced_layout.addWidget(widget, index // 3, index % 3)
        self.advanced_filters = DetailsDisclosure(summary=self.tr("Advanced filters"), parent=self)
        self.advanced_filters.add_widget(advanced_content)
        self.scaffold.add_widget(self.advanced_filters)

        actions = QWidget(self)
        actions.setObjectName("activityActions")
        actions.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.activity_actions = actions
        self._activity_action_layout = QGridLayout(actions)
        self._activity_action_layout.setContentsMargins(0, 0, 0, 0)
        self._activity_action_layout.setHorizontalSpacing(8)
        self._activity_action_layout.setVerticalSpacing(6)
        self.load_button = PrimaryButton(
            self.tr("Load"),
            description=self.tr("Read the latest records from supported local sources."),
        )
        self.load_button.setObjectName("activityLoadButton")
        self.load_button.setAccessibleName(self.tr("Load activity"))
        self.load_button.clicked.connect(lambda: self.load_activity(refresh=False))
        self.refresh_button = SecondaryButton(
            self.tr("Refresh"),
            description=self.tr("Discard the short-lived cache and reread local sources."),
        )
        self.refresh_button.setObjectName("activityRefreshButton")
        self.refresh_button.setAccessibleName(self.tr("Refresh activity sources"))
        self.refresh_button.clicked.connect(lambda: self.load_activity(refresh=True))
        self.refresh_button.setEnabled(False)
        self.load_more_button = SecondaryButton(
            self.tr("Load more"),
            description=self.tr("Read the next batch of recorded changes."),
        )
        self.load_more_button.setObjectName("activityLoadMoreButton")
        self.load_more_button.setAccessibleName(self.tr("Load more activity"))
        self.load_more_button.clicked.connect(lambda: self.load_activity(refresh=False, append=True))
        self.load_more_button.setEnabled(False)
        self.export_json_button = SecondaryButton(self.tr("JSON…"))
        self.export_json_button.setObjectName("activityExportJson")
        self.export_json_button.setAccessibleName(self.tr("Export selected activity as JSON"))
        self.export_json_button.clicked.connect(lambda: self._export_selected("json"))
        self.export_json_button.setEnabled(False)
        self.export_markdown_button = SecondaryButton(self.tr("Markdown…"))
        self.export_markdown_button.setObjectName("activityExportMarkdown")
        self.export_markdown_button.setAccessibleName(self.tr("Export selected activity as Markdown"))
        self.export_markdown_button.clicked.connect(lambda: self._export_selected("markdown"))
        self.export_markdown_button.setEnabled(False)
        self._layout_activity_actions()
        self.scaffold.add_widget(actions)

        self.feedback = QLabel(self.tr("Activity has not been loaded."))
        self.feedback.setObjectName("activityFeedback")
        self.feedback.setWordWrap(True)
        self.feedback.setAccessibleName(self.tr("Activity loading status"))
        self.scaffold.add_widget(self.feedback)
        self.source_status = QLabel()
        self.source_status.setObjectName("activitySourceStatus")
        self.source_status.setWordWrap(True)
        self.scaffold.add_widget(self.source_status)

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
        self.empty_state.body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_load_button = PrimaryButton(
            self.tr("Load activity"),
            description=self.tr("Read the latest records from supported local sources."),
        )
        self.empty_load_button.setObjectName("activityEmptyLoadButton")
        self.empty_load_button.clicked.connect(
            lambda: self.load_activity(refresh=False)
        )
        self.empty_state.body.addWidget(
            self.empty_load_button,
            0,
            Qt.AlignmentFlag.AlignHCenter,
        )
        self.scaffold.add_widget(self.empty_state, 1)

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
            self.tr("Review recovery"),
            description=self.tr("Open a fresh recovery review. This does not apply a change."),
        )
        self.review_button.setObjectName("activityReviewRecovery")
        self.review_button.clicked.connect(self._review_recovery)
        self.review_button.hide()
        self.detail_card.add_widget(self.detail_status)
        self.history_details = DetailsDisclosure(summary=self.tr("Show recorded details"))
        self.history_details.setObjectName("historyRecordedDetails")
        self.history_details.add_widget(self.detail_definitions)
        self.history_details.add_widget(self.related_label)
        self.detail_card.add_widget(self.history_details)
        self.detail_card.add_widget(self.recovery_guidance)
        self.detail_card.add_widget(self.review_button)
        self.scaffold.add_widget(self.detail_card)

    def remember_run_id(self, run_id: str) -> None:
        """Find and select one exact persisted run without substituting another."""
        self._requested_run_id = str(run_id or "").strip()[:128]
        if self._requested_run_id:
            self.feedback.setText(
                self.tr("Finding the requested run %1…")
                .replace("%1", self._requested_run_id)
            )
            if self._worker is None or not self._worker.isRunning():
                self.load_activity(refresh=False)

    def _apply_presentation_state(
        self,
        state: ActivityPresentationState,
    ) -> None:
        """Render controls only when the current data state supports them."""
        self.presentation_state = state
        self.setProperty("presentationState", state.state)
        self.feedback.setText(self.tr(state.message))
        self.table.setVisible(state.table_visible)
        self.empty_state.setVisible(state.empty_visible)
        self.detail_card.setVisible(state.details_visible)
        self.activity_actions.setVisible(state.state != "initial")
        self.feedback.setVisible(state.state != "initial")
        self.empty_load_button.setVisible(state.state == "initial")
        self.refresh_button.setEnabled(state.refresh_enabled)
        self.load_more_button.setEnabled(state.load_more_enabled)
        self.review_button.setVisible(state.recovery_review_visible)
        self.export_json_button.setEnabled(state.details_visible)
        self.export_markdown_button.setEnabled(state.details_visible)

    def load_activity(self, *, refresh: bool, append: bool = False) -> None:
        """Start one explicit, non-overlapping local collection."""
        if self._closing:
            return
        if self._worker is not None and self._worker.isRunning():
            return
        try:
            filters = (
                {"sources": ("action_center",), "search": self._requested_run_id}
                if self._requested_run_id
                else self._current_filters()
            )
        except ValueError as exc:
            self.feedback.setText(str(exc))
            self.feedback.setVisible(True)
            return
        filter_key = self._filter_key(filters)
        append = bool(
            append
            and self._next_cursor
            and self._page_filter_key == filter_key
        )
        self.load_button.set_loading(True, self.tr("Loading activity…"))
        if not append:
            self._next_cursor = None
            self._page_filter_key = filter_key
            self._apply_presentation_state(loading_state())
        worker = ActivityJournalWorker(
            self.journal_service,
            refresh=refresh,
            filters=filters,
            cursor=self._next_cursor if append else None,
            target_run_id=self._requested_run_id,
        )
        worker.setProperty("appendPage", append)
        worker.setProperty("filterKey", filter_key)
        worker.finished.connect(self._loaded)
        worker.error.connect(self._load_failed)
        self._workers.add(worker)
        _ACTIVE_JOURNAL_WORKERS.add(worker)
        workers = self._workers
        QThread.finished.__get__(worker, QThread).connect(lambda: _journal_thread_finished(worker, workers))
        self._worker = worker
        worker.start()

    def cleanup(self) -> None:
        """Disconnect page callbacks and bound shutdown without destroying a thread."""
        if self._closing:
            return
        self._closing = True
        for worker in tuple(self._workers):
            for signal, callback in ((worker.finished, self._loaded), (worker.error, self._load_failed)):
                try:
                    signal.disconnect(callback)
                except (TypeError, RuntimeError):
                    pass
        _stop_journal_workers(self._workers)
        self._worker = None

    def showEvent(self, event: Any) -> None:
        super().showEvent(event)
        if self._initial_load_started:
            return
        self._initial_load_started = True
        # Let route hand-offs set an exact run ID before the initial local read.
        QTimer.singleShot(0, self._load_initial_local_activity)

    def _load_initial_local_activity(self) -> None:
        if self._closing or self._snapshot is not None or (self._worker is not None and self._worker.isRunning()):
            return
        if not self._requested_run_id:
            history_index = self.activity_view_filter.findData("history")
            self.activity_view_filter.setCurrentIndex(history_index)
            local_index = self.source_filter.findData("local_loofi")
            self.source_filter.setCurrentIndex(local_index)
        self.load_activity(refresh=False)

    def closeEvent(self, event: QCloseEvent | None) -> None:
        self.cleanup()
        super().closeEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_activity_actions()

    def _layout_activity_actions(self) -> None:
        """Wrap action controls when their current font no longer fits one row."""
        if not hasattr(self, "_activity_action_layout"):
            return
        buttons = (
            self.refresh_button,
            self.load_more_button,
            self.export_json_button,
            self.export_markdown_button,
            self.load_button,
        )
        layout = self._activity_action_layout
        needed = sum(button.sizeHint().width() for button in buttons) + layout.horizontalSpacing() * (len(buttons) - 1)
        wrap = self.activity_actions.width() > 0 and needed > self.activity_actions.width()
        for button in buttons:
            layout.removeWidget(button)
        for column in range(len(buttons) + 1):
            layout.setColumnStretch(column, 0)
        if wrap:
            layout.addWidget(self.refresh_button, 0, 0)
            layout.addWidget(self.load_more_button, 0, 1)
            layout.addWidget(self.load_button, 0, 2)
            layout.addWidget(self.export_json_button, 1, 0)
            layout.addWidget(self.export_markdown_button, 1, 1)
            layout.setColumnStretch(3, 1)
        else:
            layout.addWidget(self.refresh_button, 0, 0)
            layout.addWidget(self.load_more_button, 0, 1)
            layout.addWidget(self.export_json_button, 0, 2)
            layout.addWidget(self.export_markdown_button, 0, 3)
            layout.addWidget(self.load_button, 0, 5)
            layout.setColumnStretch(4, 1)

    def _loaded(self, result: object) -> None:
        if self._closing:
            return
        if not isinstance(result, ChangeJournalSnapshot):
            self._load_failed(self.tr("The activity source returned an invalid result."))
            return
        if self._requested_run_id and self._worker is not None and self._worker.target_run_id != self._requested_run_id:
            self._worker = None
            QTimer.singleShot(0, lambda: self.load_activity(refresh=False))
            return
        requested_filter_key = (
            self._worker.property("filterKey")
            if self._worker is not None
            else None
        )
        try:
            current_filters = (
                {"sources": ("action_center",), "search": self._requested_run_id}
                if self._requested_run_id
                else self._current_filters()
            )
            current_filter_key = self._filter_key(current_filters)
        except ValueError as exc:
            self._load_failed(str(exc))
            return
        if requested_filter_key is not None and requested_filter_key != current_filter_key:
            self._worker = None
            self._next_cursor = None
            self._page_filter_key = None
            self.load_button.reset_state()
            self.load_button.setText(
                self.tr("Load again") if self._snapshot is not None else self.tr("Load activity")
            )
            self._apply_presentation_state(
                snapshot_state(self._snapshot) if self._snapshot is not None else initial_state()
            )
            self.feedback.setText(
                self.tr("Filters changed while loading. Load again to use the new filters.")
            )
            self.load_more_button.setEnabled(False)
            return
        append = bool(self._worker and self._worker.property("appendPage"))
        selected_event = self._selected_event() if append else None
        selected_id = selected_event.event_id if selected_event is not None else None
        if append and self._snapshot is not None:
            merged_events = tuple(self._snapshot.events) + tuple(
                event for event in result.events if event.event_id not in self._events_by_id
            )
            result = ChangeJournalSnapshot(
                events=merged_events,
                sources=result.sources,
                generated_at=result.generated_at,
                truncated=result.truncated,
                schema=result.schema,
                next_cursor=result.next_cursor,
            )
        self._snapshot = result
        self._next_cursor = result.next_cursor
        self._page_filter_key = requested_filter_key or current_filter_key
        self._events_by_id = {event.event_id: event for event in result.events}
        self.load_button.reset_state()
        self.load_button.setText(self.tr("Load again"))
        self._apply_presentation_state(snapshot_state(result))
        self.source_status.setText(self._source_status_text(result))
        self._render_events(result.events, selected_event_id=selected_id)
        if self._requested_run_id:
            requested = self._requested_run_id
            matching = next((event for event in result.events if str(event.after_facts.get("run_id", "")) == requested), None)
            if matching is None:
                self.feedback.setText(self.tr("The requested run %1 could not be found in local Activity records.").replace("%1", requested))
                self.feedback.setVisible(True)
            else:
                self._requested_run_id = ""
                self._select_event(matching.event_id)
                self.feedback.setText(self.tr("Opened requested run %1.").replace("%1", requested))
                self.feedback.setVisible(True)
        self._worker = None

    def _select_event(self, event_id: str) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and str(item.data(Qt.ItemDataRole.UserRole)) == event_id:
                self.table.selectRow(row)
                self.table.setCurrentCell(row, 0)
                self._render_selected()
                return

    def _filters_changed(self, *_args: object) -> None:
        """Invalidate continuation cursors when the query changes."""
        self._next_cursor = None
        self._page_filter_key = None
        self.load_more_button.setEnabled(False)

    @staticmethod
    def _filter_key(filters: Mapping[str, Any]) -> tuple[tuple[str, Any], ...]:
        return tuple(sorted(filters.items()))

    def _load_failed(self, message: str) -> None:
        if self._closing:
            return
        self.load_button.reset_state()
        self._apply_presentation_state(
            error_state(
                str(message),
                has_snapshot=self._snapshot is not None,
                has_events=bool(self._snapshot and self._snapshot.events),
            )
        )
        self._worker = None

    def _render_events(self, events: tuple[ChangeEvent, ...], *, selected_event_id: str | None = None) -> None:
        self.table.setRowCount(0)
        if not events:
            self.empty_state.title_label.setText(self.tr("No recorded changes"))
            self.empty_state.set_message(
                self.tr("The available sources did not report any changes.")
            )
            return
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
            if selected_event_id == event.event_id:
                self.table.selectRow(row)

    def _selected_event(self) -> ChangeEvent | None:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        event_id = str(item.data(Qt.ItemDataRole.UserRole)) if item is not None else ""
        return self._events_by_id.get(event_id)

    def _render_selected(self) -> None:
        event = self._selected_event()
        if event is None:
            return
        self._apply_presentation_state(selected_state(event))
        self.load_more_button.setEnabled(bool(self._next_cursor))
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
        self.detail_definitions.add_row(self.tr("Expected"), self._facts_text(event.after_facts.get("expected")))
        self.detail_definitions.add_row(self.tr("Before"), self._facts_text(event.before_facts))
        self.detail_definitions.add_row(self.tr("After"), self._facts_text(event.after_facts))
        self.detail_definitions.add_row(self.tr("Verification"), self._facts_text(event.after_facts.get("verification")))
        self.detail_definitions.add_row(self.tr("Recovery"), self._facts_text(event.after_facts.get("recovery")))
        related = len(event.correlation_ids)
        self.related_label.setText(
            self.tr("Possibly related: %1 change(s). This is a time-and-resource match, not proof of cause.")
            .replace("%1", str(related))
        )
        recovery = event.recovery
        if recovery.kind == "action_center":
            self.detail_status.set_status(
                self.tr("Recovery can be reviewed"),
                kind="warning",
                description=self.tr("Current state will be checked again before a plan is created."),
            )
            self.recovery_guidance.setText(
                recovery.guidance or self.tr("Review this recovery in the supported workflow.")
            )
        elif recovery.kind == "manual_guidance":
            self.detail_status.set_status(self.tr("Manual recovery guidance"), kind="neutral")
            self.recovery_guidance.setText(recovery.guidance)
        else:
            self.detail_status.set_status(self.tr("No supported recovery"), kind="neutral")
            self.recovery_guidance.setText(
                recovery.guidance or self.tr("This record is available for review only.")
            )

    def _current_filters(self) -> dict[str, object]:
        """Return bounded UI filters; accept ISO dates and Unix timestamps."""
        filters: dict[str, object] = {}
        source = str(self.source_filter.currentData() or "")
        state = str(self.status_filter.currentData() or "")
        view = str(self.activity_view_filter.currentData() or "needs_you")
        reboot = str(self.reboot_filter.currentData() or "")
        search = self.search_input.text().strip()[:120]
        if source == "local_loofi":
            filters["sources"] = ("action_center", "loofi_app")
        elif source:
            filters["sources"] = (source,)
        if state:
            filters["statuses"] = (state,)
        elif view and not (source == "local_loofi" and view == "history"):
            view_statuses = {
                "needs_you": ("failed", "verification_failed", "awaiting_reboot", "interrupted"),
                "in_progress": ("running", "verifying"),
                "history": ("succeeded", "cancelled", "recorded"),
            }
            if view in view_statuses:
                filters["statuses"] = view_statuses[view]
        if reboot:
            filters["reboot_required"] = reboot == "required"
        if search:
            filters["search"] = search
        for field, widget in (("since", self.since_input), ("until", self.until_input)):
            value = widget.text().strip()
            if not value:
                continue
            try:
                timestamp = float(value)
            except ValueError:
                try:
                    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
                except (ValueError, OverflowError, OSError) as exc:
                    raise ValueError(self.tr("Date filters must use YYYY-MM-DD or Unix timestamps.")) from exc
            if not math.isfinite(timestamp):
                raise ValueError(self.tr("Date filters must contain finite Unix timestamps."))
            filters[field] = timestamp
        since, until = filters.get("since"), filters.get("until")
        if isinstance(since, float) and isinstance(until, float) and since > until:
            raise ValueError(self.tr("The since date must not be later than the until date."))
        return filters

    def _source_status_text(self, snapshot: ChangeJournalSnapshot) -> str:
        statuses = [
            f"{self._SOURCE_LABELS.get(item.source, item.source)}: {item.availability}"
            for item in snapshot.sources
        ]
        return self.tr("Source availability: %1").replace("%1", "; ".join(statuses))

    @staticmethod
    def _facts_text(value: object) -> str:
        if not value:
            return "Not recorded"
        if isinstance(value, Mapping):
            return "; ".join(f"{key}={item}" for key, item in list(value.items())[:12])
        return str(value)[:600]

    def _export_selected(self, format_name: str) -> None:
        event = self._selected_event()
        if event is None:
            return
        suffix = "json" if format_name == "json" else "md"
        destination, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Export activity event"),
            f"activity-{event.event_id.replace(':', '-')}.{suffix}",
            self.tr("JSON (*.json);;Markdown (*.md)"),
        )
        if not destination:
            return
        try:
            content = self.journal_service.export_event(event.event_id, format=format_name)
            Path(destination).write_text(content, encoding="utf-8")
            self.feedback.setText(self.tr("Exported selected event."))
        except (OSError, KeyError, TypeError, ValueError) as exc:
            self.feedback.setText(self.tr("Export failed: %1").replace("%1", str(exc)))

    def _review_recovery(self) -> None:
        event = self._selected_event()
        if event is None or event.recovery.kind != "action_center":
            return
        self.actionCenterRequested.emit(
            str(event.recovery.action_id),
            dict(event.recovery.parameters),
        )
