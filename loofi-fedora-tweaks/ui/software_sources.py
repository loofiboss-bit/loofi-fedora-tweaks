"""Searchable, asynchronous local DNF source configuration overview."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHeaderView, QLabel, QLineEdit, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from core.privacy import redact_text
from services.software.source_status import DnfSourceSnapshot, SoftwareSourceStatusService, SourceStatusReason
from ui.operation_worker import OperationControllerQtAdapter


class SoftwareSourcesWidget(QWidget):
    """Read-only overview; emits the observation for existing source badges."""

    snapshotChanged = pyqtSignal(object)
    stopped = pyqtSignal()

    def __init__(self, service: SoftwareSourceStatusService | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service or SoftwareSourceStatusService()
        self.snapshot: DnfSourceSnapshot | None = None
        self.setObjectName("softwareSources")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        note = QLabel(self.tr("Configured DNF package sources. This reads local configuration; network availability is not checked."))
        note.setWordWrap(True)
        layout.addWidget(note)
        self.search = QLineEdit()
        self.search.setPlaceholderText(self.tr("Search package sources"))
        self.search.setAccessibleName(self.tr("Search package sources"))
        self.search.textChanged.connect(self._filter)
        layout.addWidget(self.search)
        self.status = QLabel(self.tr("Sources have not been checked."))
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status)
        self.table = QTreeWidget()
        self.table.setHeaderLabels([self.tr("Source ID"), self.tr("Name"), self.tr("Status")])
        self.table.setRootIsDecorated(False)
        header = self.table.header()
        if header is not None:
            header.setStretchLastSection(False)
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setColumnWidth(0, 260)
        self.table.setAccessibleName(self.tr("Configured DNF package sources"))
        self.table.setMinimumHeight(160)
        layout.addWidget(self.table)
        self.refresh_button = QPushButton(self.tr("Refresh package sources"))
        self.refresh_button.clicked.connect(self.refresh)
        layout.addWidget(self.refresh_button)
        self._adapter = OperationControllerQtAdapter(parent=self)
        self._adapter.finished.connect(self.set_snapshot)
        self._adapter.failed.connect(self._failed)
        self._adapter.stopped.connect(lambda: self.refresh_button.setEnabled(True))
        self._adapter.stopped.connect(self.stopped.emit)

    @property
    def busy(self) -> bool:
        return self._adapter.busy

    def request_stop(self) -> None:
        """Request cancellation; the bounded active read is allowed to finish."""
        self._adapter.cancel()

    def cleanup(self, timeout_ms: int = 1000) -> bool:
        """Keep running worker ownership in the adapter until its query exits."""
        self.request_stop()
        return self._adapter.close(timeout_ms)

    def refresh(self) -> None:
        if self._adapter.busy:
            return
        self.refresh_button.setEnabled(False)
        self.status.setText(self.tr("Reading local package sources…"))
        self._adapter.start(self.service.sources_snapshot)

    def _failed(self, _message: str) -> None:
        self.set_snapshot(DnfSourceSnapshot("", reason=SourceStatusReason.PROBE_FAILED))

    def set_snapshot(self, snapshot: object) -> None:
        if not isinstance(snapshot, DnfSourceSnapshot):
            self._failed("")
            return
        self.snapshot = snapshot
        self.table.clear()
        reasons = {
            SourceStatusReason.TOOL_UNAVAILABLE: self.tr("DNF5 is not installed."),
            SourceStatusReason.UNSUPPORTED_BACKEND: self.tr("This source overview requires traditional Fedora with DNF5."),
            SourceStatusReason.TIMEOUT: self.tr("The source query timed out."),
            SourceStatusReason.COMMAND_FAILED: self.tr("DNF5 could not read the source configuration."),
            SourceStatusReason.INVALID_RESPONSE: self.tr("DNF5 returned an invalid source list."),
            SourceStatusReason.PROBE_FAILED: self.tr("The source configuration could not be inspected."),
        }
        if snapshot.success:
            self.status.setText(self.tr("Observed: {time} · Configured sources: {count}").format(time=snapshot.observed_at, count=len(snapshot.repositories)))
            for repo in snapshot.repositories:
                item = QTreeWidgetItem([
                    redact_text(repo.source_id), redact_text(repo.name), self.tr("Enabled") if repo.enabled else self.tr("Disabled"),
                ])
                for column in range(3):
                    item.setToolTip(column, item.text(column))
                self.table.addTopLevelItem(item)
        else:
            self.status.setText(self.tr("Unknown: {reason} · Observed: {time}").format(
                reason=reasons.get(snapshot.reason or SourceStatusReason.PROBE_FAILED, reasons[SourceStatusReason.PROBE_FAILED]), time=snapshot.observed_at or self.tr("Not available"),
            ))
        self._filter(self.search.text())
        self.snapshotChanged.emit(snapshot)

    def _filter(self, query: str) -> None:
        needle = query.strip().casefold()
        for index in range(self.table.topLevelItemCount()):
            row = self.table.topLevelItem(index)
            if row is None:
                continue
            row.setHidden(needle not in " ".join(row.text(column) for column in range(3)).casefold())
