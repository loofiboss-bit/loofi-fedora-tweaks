"""Read-only local metadata and explicit runtime cleanup review presentation."""
from __future__ import annotations

from PyQt6.QtCore import QProcess, Qt, pyqtSignal
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


class FlatpakAccessDialog(QDialog):
    """Present captured, privacy-filtered layers and explicit native handoffs."""

    def __init__(self, app, report, parent=None, *, handoffs=(), launch_requested=None):
        super().__init__(parent)
        from core.catalog_models import NativeHandoffId
        from ui.native_handoff_card import NativeHandoffCard
        self.setWindowTitle(self.tr("Understand app access"))
        self.resize(760, 650)
        layout = QVBoxLayout(self)
        identity = QLabel(self.tr("Ref: %1\nInstallation: %2\nStatus: %3").replace("%1", report.ref).replace("%2", report.installation).replace("%3", report.status))
        identity.setWordWrap(True)
        layout.addWidget(identity)
        notice = QLabel(self.tr(report.notice))
        notice.setWordWrap(True)
        layout.addWidget(notice)
        if report.error:
            layout.addWidget(QLabel(self.tr(report.error)))
        from PyQt6.QtWidgets import QScrollArea, QWidget
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        titles = {"declared": self.tr("Declared application metadata"), "global-overrides": self.tr("Global overrides"), "app-overrides": self.tr("Application ID overrides")}
        for layer in report.layers:
            text = "\n".join(f"[{entry.category}] {entry.key}: {entry.value}\n{self.tr(entry.explanation)}" for entry in layer.entries)
            if layer.status != "available":
                text = self.tr(layer.error)
            elif not text:
                text = self.tr("No entries were reported in this layer.")
            disclosure = DetailsDisclosure(text, summary=f"{titles[layer.kind]} · {layer.installation} · {layer.status}")
            disclosure.setAccessibleName(disclosure.toggle_button.text())
            body_layout.addWidget(disclosure)
        cached = {item.target.handoff_id: item for item in handoffs}
        for handoff_id, title in ((NativeHandoffId.FLATPAK_PERMISSIONS, self.tr("KDE Flatpak permissions")), (NativeHandoffId.FLATSEAL, self.tr("Flatseal"))):
            card = NativeHandoffCard(handoff_id, title=title,
                                     description=self.tr("Review changes in the installed permission tool. These tools manage application IDs; select the app and installation there."),
                                     button_text=self.tr("Open permission tool"), parent=self)
            body_layout.addWidget(card)
            # Captured availability comes from the page worker; construction never probes.
            card.open_button.clicked.disconnect()
            observed = cached.get(handoff_id)
            if observed is not None:
                card.open_button.setEnabled(observed.available and launch_requested is not None)
                card.status_label.setText(observed.detail)
                card.status_label.setAccessibleName(observed.detail)
                card.setProperty("capabilityState", observed.state.value)
            else:
                card.status_label.setText(self.tr("Permission tool availability could not be checked. Use desktop settings or inspect Flatpak overrides manually."))
            if launch_requested is not None:
                card.open_button.clicked.connect(lambda _checked=False, selected=handoff_id: launch_requested(self, selected))
        scroll.setWidget(body)
        layout.addWidget(scroll)
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
        self.access_stop_button = QPushButton(self.tr("Cancel app access inspection"))
        self.access_stop_button.clicked.connect(self.request_stop)
        self.access_stop_button.hide()
        self.add_widget(self.access_stop_button)
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

    def show_access(self, app):
        if self.busy:
            self.status.setText(self.tr("Wait for the current inspection to finish, then inspect app access."))
            return
        for dialog in tuple(self._dialogs.values()):
            dialog.close()
        self._dialogs.clear()
        self._generation += 1
        generation = self._generation
        self._active_generation = generation
        self.status.setText(self.tr("Reading application access and permission tool availability…"))
        self.access_stop_button.show()

        def capture():
            from core.catalog_models import NativeHandoffId
            from services.desktop.native_handoff import NativeHandoffService
            from services.software.flatpak_access import FlatpakAccessService
            from services.system.system import SystemManager
            report = FlatpakAccessService(cancelled=lambda: self._adapter.cancel_requested).inspect(app.ref, app.installation)
            handoffs = []
            service = NativeHandoffService(probe_timeout=0.75)
            for handoff_id in (NativeHandoffId.FLATPAK_PERMISSIONS, NativeHandoffId.FLATSEAL):
                if self._adapter.cancel_requested:
                    break
                handoffs.append(service.availability(handoff_id, profile=SystemManager.get_platform_profile()))
            return "access", generation, app, (report, tuple(handoffs))

        self._adapter.start(capture)

    def _access_closed(self, generation):
        self._dialogs.pop(generation, None)
        if generation == self._generation:
            self._generation += 1
            self._adapter.cancel()

    def _launch_access_tool(self, dialog, handoff_id):
        if self.busy or self._dialogs.get(self._generation) is not dialog:
            return
        generation = self._generation
        self._active_generation = generation
        self.status.setText(self.tr("Checking the permission tool before opening it…"))

        def prepare():
            from services.desktop.native_handoff import NativeHandoffService
            from services.system.system import SystemManager
            launch = None
            if not self._adapter.cancel_requested:
                launch = NativeHandoffService(probe_timeout=0.75).prepare_launch(
                    handoff_id, profile=SystemManager.get_platform_profile(),
                )
            return "access-launch", generation, dialog, launch

        self._adapter.start(prepare)

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
        if kind == "access-launch":
            if self._dialogs.get(generation) is not app:
                return
            if metadata is None:
                self.status.setText(self.tr("The permission tool is unavailable. Inspect desktop settings or Flatpak overrides manually."))
                return
            result = QProcess.startDetached(metadata.program, list(metadata.arguments))
            started = result[0] if isinstance(result, tuple) else bool(result)
            self.status.setText(self.tr("Permission tool opened.") if started else self.tr("The permission tool could not be started."))
            return
        if kind == "access":
            report, handoffs = metadata
            dialog = FlatpakAccessDialog(app, report, self, handoffs=handoffs, launch_requested=self._launch_access_tool)
            self._dialogs[generation] = dialog
            dialog.finished.connect(lambda _result, key=generation: self._access_closed(key))
            dialog.open()
            self.status.setText(self.tr("Application access checked; see the captured layer status in the dialog."))
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
        self.access_stop_button.hide()
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
