"""Read-only local metadata and explicit runtime cleanup review presentation."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout

from ui.components import Card, DetailsDisclosure
from ui.operation_worker import OperationControllerQtAdapter


class AppDetailsDialog(QDialog):
    def __init__(self, app, details, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("App details"))
        self.setAccessibleName(self.tr("App details for %1").replace("%1", app.name))
        self.resize(680, 480)
        layout = QVBoxLayout(self)
        lines = [self.tr("Name: %1").replace("%1", details.name or app.name),
                 self.tr("Version: %1").replace("%1", details.version or self.tr("Not reported")),
                 self.tr("Installation: %1").replace("%1", details.installation),
                 self.tr("Source remote: %1").replace("%1", details.origin or self.tr("Not reported")),
                 self.tr("Reference: %1").replace("%1", details.ref),
                 self.tr("Runtime: %1").replace("%1", details.runtime or self.tr("Not reported")),
                 self.tr("Reported size: %1").replace("%1", str(details.size_bytes) + " B" if details.size_bytes is not None else self.tr("Unknown"))]
        for title, warning, rebase in ((self.tr("Application"), details.eol, details.eol_rebase),
                                       (self.tr("Runtime"), details.runtime_eol, details.runtime_eol_rebase)):
            lines.append(self.tr("%1: %2").replace("%1", title).replace("%2", warning or self.tr("No local EOL warning reported; continued support is not guaranteed.")))
            if rebase:
                lines.append(self.tr("Replacement ref: %1").replace("%1", rebase))
        if details.runtime_missing:
            lines.append(self.tr("The declared runtime is missing from this installation."))
        disclosure = DetailsDisclosure("\n".join(lines), summary=self.tr("Local application metadata"))
        disclosure.setAccessibleName(self.tr("Local application metadata"))
        disclosure.toggle_button.setChecked(True)
        layout.addWidget(disclosure, 1)
        notice = QLabel(self.tr("Reported installation sizes include shared objects and do not predict freed space."))
        notice.setWordWrap(True)
        layout.addWidget(notice)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout.addWidget(close)


class FlatpakInsightsCard(Card):
    actionReviewRequested = pyqtSignal(str, object)
    stopped = pyqtSignal()

    def __init__(self, service=None, parent=None):
        super().__init__(self.tr("Unused Flatpak runtimes"), self.tr("Inspect one installation, then select exact runtimes for review."))
        self.service = service
        self.installation = QComboBox()
        self.installation.setEditable(True)
        self.installation.setAccessibleName(self.tr("Runtime installation"))
        self.installation.addItems(["user", "system"])
        self.installation.currentTextChanged.connect(self.invalidate)
        self.add_widget(self.installation)
        self.discover_button = QPushButton(self.tr("Refresh installations"))
        self.discover_button.setEnabled(service is not None)
        self.discover_button.clicked.connect(self.discover_installations)
        self.add_widget(self.discover_button)
        self.inspect_button = QPushButton(self.tr("Inspect unused runtimes"))
        self.inspect_button.setEnabled(service is not None)
        self.inspect_button.clicked.connect(self.inspect)
        self.add_widget(self.inspect_button)
        self.status = QLabel(self.tr("Runtime status has not been checked."))
        self.status.setWordWrap(True)
        self.add_widget(self.status)
        self.entries = QListWidget()
        self.entries.setAccessibleName(self.tr("Select unused runtimes for review"))
        self.entries.setMinimumHeight(120)
        self.add_widget(self.entries)
        self.review_button = QPushButton(self.tr("Review runtime cleanup"))
        self.review_button.setEnabled(False)
        self.review_button.clicked.connect(self.review)
        self.entries.itemChanged.connect(self._selection_changed)
        self.add_widget(self.review_button)
        self._snapshot = None
        self._generation = 0
        self._active_generation = 0
        self._pending_details = None
        self._dialogs = {}
        self._adapter = OperationControllerQtAdapter(parent=self)
        self._adapter.finished.connect(self._result)
        self._adapter.failed.connect(self._failed)
        self._adapter.stopped.connect(self._stopped)

    @property
    def busy(self):
        return self._adapter.busy

    def set_installations(self, installations):
        current = self.installation.currentText()
        self.installation.blockSignals(True)
        self.installation.clear()
        self.installation.addItems(sorted({"user", "system", *installations}))
        self.installation.setCurrentText(current)
        self.installation.blockSignals(False)

    def invalidate(self):
        self._generation += 1
        self._snapshot = None
        self.entries.clear()
        self.review_button.setEnabled(False)
        self.status.setText(self.tr("Inspect this installation before reviewing cleanup."))

    def discover_installations(self):
        if self.service is None or self.busy:
            return
        self.invalidate()
        self._pending_details = None
        self._active_generation = self._generation
        generation = self._generation
        self._adapter.start(lambda: ("installations", generation, None, self.service.installations()))

    def inspect(self):
        if self.service is None or self.busy:
            return
        self.invalidate()
        self._pending_details = None
        generation = self._generation
        installation = self.installation.currentText()
        self._active_generation = generation
        self.inspect_button.setEnabled(False)
        self.status.setText(self.tr("Reading local runtime metadata…"))
        self._adapter.start(lambda: ("unused", generation, None, self.service.unused(installation)))

    def show_details(self, app):
        if self.service is None:
            return
        for dialog in tuple(self._dialogs.values()):
            dialog.close()
        self._dialogs.clear()
        self._generation += 1
        self._pending_details = (app, self._generation)
        if self.busy:
            self._adapter.cancel()
        else:
            self._start_details()

    def _start_details(self):
        if self.busy or self._pending_details is None:
            return
        app, generation = self._pending_details
        self._pending_details = None
        self._active_generation = generation
        self._adapter.start(lambda: ("details", generation, app, self.service.details(app)))

    def _result(self, result):
        kind, generation, app, metadata = result
        if generation != self._generation:
            return
        if kind == "installations":
            self.set_installations(metadata)
            self.status.setText(self.tr("Select an installation before inspection. You can also enter a named installation."))
            return
        if not metadata.available:
            self.status.setText(metadata.error or self.tr("Local Flatpak metadata is unavailable."))
            return
        if kind == "details":
            dialog = AppDetailsDialog(app, metadata, self)
            self._dialogs[generation] = dialog
            dialog.finished.connect(lambda _result, key=generation: self._dialogs.pop(key, None))
            dialog.open()
            return
        self._snapshot = metadata
        self.entries.clear()
        for ref in metadata.refs:
            size = self.tr("Unknown size") if ref.size_bytes is None else str(ref.size_bytes) + " B"
            item = QListWidgetItem(f"{ref.ref} · {size}")
            item.setData(Qt.ItemDataRole.UserRole, ref.ref)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.entries.addItem(item)
        notice = self.tr("Reported sizes do not predict freed space. App data is preserved. Recovery is manual reinstallation.")
        if metadata.installation != "user":
            notice += "\n" + self.tr("Shared installation: other users' private app inventories have not been inspected.")
        self.status.setText((metadata.warning + "\n" if metadata.warning else "") + (notice if metadata.refs else self.tr("No unused runtimes were reported.")))

    def _selection_changed(self):
        self.review_button.setEnabled(self._snapshot is not None and bool(self.selected_refs()))

    def selected_refs(self):
        return [self.entries.item(index).data(Qt.ItemDataRole.UserRole) for index in range(self.entries.count())
                if self.entries.item(index).checkState() == Qt.CheckState.Checked]

    def review(self):
        if self._snapshot is None or not self.selected_refs():
            return
        self.actionReviewRequested.emit("remove-unused-flatpaks", {
            "installation": self._snapshot.installation, "refs": self.selected_refs(), "snapshot_digest": self._snapshot.digest,
        })

    def _failed(self, _message):
        if self._active_generation == self._generation:
            self.status.setText(self.tr("Local Flatpak metadata could not be read."))

    def _stopped(self):
        self.inspect_button.setEnabled(self.service is not None)
        self._start_details()
        if not self.busy:
            self.stopped.emit()

    def request_stop(self):
        self._generation += 1
        self._pending_details = None
        self._adapter.cancel()
        for dialog in tuple(self._dialogs.values()):
            dialog.close()
        self._dialogs.clear()

    def cleanup(self, timeout_ms=1000):
        self.request_stop()
        return self._adapter.close(timeout_ms)
