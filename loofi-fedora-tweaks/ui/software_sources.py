"""Searchable, asynchronous local DNF source configuration overview."""

from __future__ import annotations

import re

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QCheckBox, QComboBox, QHeaderView, QLabel, QLineEdit, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from core.privacy import redact_text
from services.software.source_status import DnfSourceSnapshot, SoftwareSourceStatusService, SourceStatusReason
from ui.operation_worker import OperationControllerQtAdapter


class SoftwareSourcesWidget(QWidget):
    """Read-only overview; emits the observation for existing source badges."""

    _SOURCE_ID = re.compile(r"^[A-Za-z0-9_.:+-]{1,128}$")

    snapshotChanged = pyqtSignal(object)
    actionReviewRequested = pyqtSignal(str, object)
    stopped = pyqtSignal()

    def __init__(self, service: SoftwareSourceStatusService | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service or SoftwareSourceStatusService()
        self.snapshot: DnfSourceSnapshot | None = None
        self._focus_source_id = ""
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
        setup_note = QLabel(self.tr("Optional setup: choose a source explicitly, then review its signing trust and scope. Source activation and codec installation are separate operations."))
        setup_note.setWordWrap(True)
        layout.addWidget(setup_note)
        self.setup_source = QComboBox()
        self.setup_source.setAccessibleName(self.tr("Optional software source"))
        self.setup_source.addItem(self.tr("Choose an optional source…"), "")
        self.setup_source.addItem(self.tr("Flathub"), "flathub")
        self.setup_source.addItem(self.tr("RPM Fusion Free"), "rpmfusion-free")
        self.setup_source.addItem(self.tr("RPM Fusion Nonfree"), "rpmfusion-nonfree")
        layout.addWidget(self.setup_source)
        self.setup_scope = QComboBox()
        self.setup_scope.setAccessibleName(self.tr("Source installation scope"))
        layout.addWidget(self.setup_scope)
        self.setup_trust = QLabel()
        self.setup_trust.setTextFormat(Qt.TextFormat.PlainText)
        self.setup_trust.setWordWrap(True)
        self.setup_trust.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.setup_trust)
        self.setup_review = QPushButton(self.tr("Review source activation"))
        self.setup_review.clicked.connect(self._review_setup_source)
        layout.addWidget(self.setup_review)
        self.codec_help = QLabel(self.tr("Enable RPM Fusion Free, then download RPM metadata before creating a fresh codec review. The review lists every removal."))
        self.codec_help.setWordWrap(True)
        layout.addWidget(self.codec_help)
        self.metadata_review = QPushButton(self.tr("Review RPM metadata download"))
        self.metadata_review.clicked.connect(lambda: self.actionReviewRequested.emit("refresh-application-metadata", {"source": "fedora"}))
        layout.addWidget(self.metadata_review)
        self.codec_consent = QCheckBox(self.tr("Review predefined FFmpeg replacements"))
        self.codec_consent.setChecked(False)
        layout.addWidget(self.codec_consent)
        self.codec_review = QPushButton(self.tr("Review optional FFmpeg/GStreamer codecs"))
        self.codec_review.clicked.connect(lambda: self.actionReviewRequested.emit("install-multimedia-codecs", {"removal_consent": self.codec_consent.isChecked()}))
        layout.addWidget(self.codec_review)
        self.setup_source.currentIndexChanged.connect(self._setup_source_changed)
        self.setup_scope.currentIndexChanged.connect(self._setup_scope_changed)
        self._setup_source_changed()
        self._adapter = OperationControllerQtAdapter(parent=self)
        self._adapter.finished.connect(self.set_snapshot)
        self._adapter.failed.connect(self._failed)
        self._adapter.stopped.connect(lambda: self.refresh_button.setEnabled(True))
        self._adapter.stopped.connect(self.stopped.emit)

    def _setup_source_changed(self) -> None:
        from services.software.setup_sources import SOURCES

        self.setup_scope.clear()
        self.setup_scope.addItem(self.tr("Choose an installation scope…"), "")
        definition = SOURCES.get(self.setup_source.currentData())
        if definition is None:
            self.setup_trust.setText(self.tr("No optional source is selected."))
        else:
            for scope in definition.scopes:
                self.setup_scope.addItem(self.tr("This user") if scope == "user" else self.tr("Whole computer"), scope)
            self.setup_trust.setText(self.tr("Provider: {provider}\nURL: {url}\nSigning fingerprints: {keys}\nTrust definition: {version}").format(
                provider=definition.provider, url=definition.url, keys=" · ".join(definition.fingerprints), version=definition.to_dict()["definition_version"]))
        self._setup_scope_changed()

    def _setup_scope_changed(self) -> None:
        self.setup_review.setEnabled(bool(self.setup_source.currentData() and self.setup_scope.currentData()))

    def _review_setup_source(self) -> None:
        source, scope = self.setup_source.currentData(), self.setup_scope.currentData()
        if not source or not scope:
            return
        self.actionReviewRequested.emit("enable-flathub" if source == "flathub" else "enable-rpm-fusion",
                                        {"scope": scope} if source == "flathub" else {"source_id": source})

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
        if self._focus_source_id:
            self._select_exact_source(self._focus_source_id)
        self.snapshotChanged.emit(snapshot)

    def focus_source(self, source_id: str) -> bool:
        """Filter to and select one validated repository ID without probing."""
        value = str(source_id or "").strip()
        if not self._SOURCE_ID.fullmatch(value):
            self._focus_source_id = ""
            self.search.clear()
            self.search.setFocus()
            return False
        self._focus_source_id = value
        self.search.setText(value)
        return self._select_exact_source(value)

    def _select_exact_source(self, source_id: str) -> bool:
        for index in range(self.table.topLevelItemCount()):
            row = self.table.topLevelItem(index)
            if row is not None and row.text(0) == source_id:
                self.table.setCurrentItem(row)
                self.table.scrollToItem(row)
                self.table.setFocus()
                return True
        self.search.setFocus()
        return False

    def _filter(self, query: str) -> None:
        if query.strip() != self._focus_source_id:
            self._focus_source_id = ""
        needle = query.strip().casefold()
        for index in range(self.table.topLevelItemCount()):
            row = self.table.topLevelItem(index)
            if row is None:
                continue
            row.setHidden(needle not in " ".join(row.text(column) for column in range(3)).casefold())
