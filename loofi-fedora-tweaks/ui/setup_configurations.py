"""Portable setup library page backed by existing reviewed app/profile flows."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QSortFilterProxyModel, Qt, pyqtSignal
from PyQt6.QtGui import QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTabWidget, QTableView, QVBoxLayout, QWidget,
)

from core.plugins.interface import PluginInterface
from core.plugins.metadata import PluginMetadata
from core.product_catalog import plugin_metadata_for_module
from core.tasks.setup_configurations import (
    SetupApplication, SetupDocument, SetupLibrary, SetupProgressStore, parse_setup, serialize_setup, setup_app_from_installed,
)
from core.tasks.tweak_profiles import TweakProfile
from core.tasks.tweaks import TweakState
from services.software.installed_applications import InstalledApplication, InstalledInventory


class SetupConfigurationsPage(QWidget):
    """Inspect selected applications and user settings; mutations go to the shell."""

    continueSetupRequested = pyqtSignal(str, str)
    refreshRequested = pyqtSignal()
    routeRequested = pyqtSignal(str, object)
    compareRequested = pyqtSignal(str)
    applyRequested = pyqtSignal(str)
    importRequested = pyqtSignal(object)
    profileReviewRequested = pyqtSignal(str, object)
    bundleReviewRequested = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("setupConfigurationsPage")
        self.setAccessibleName(self.tr("My Fedora configuration"))
        root = QVBoxLayout(self)
        title = QLabel(self.tr("My Fedora configuration"))
        title.setObjectName("pageTitle")
        root.addWidget(title)
        description = QLabel(self.tr("Save apps and supported settings, compare them with this computer, and review each change."))
        description.setWordWrap(True)
        root.addWidget(description)
        top = QHBoxLayout()
        self.back_button = QPushButton(self.tr("Overview"))
        self.back_button.setAccessibleName(self.tr("Return to Overview"))
        self.back_button.setToolTip(self.tr("Return to Overview"))
        self.back_button.clicked.connect(lambda: self._navigate("overview"))
        top.addWidget(self.back_button)
        self.refresh_button = QPushButton(self.tr("Read computer"))
        self.refresh_button.setAccessibleName(self.tr("Read this computer"))
        self.refresh_button.setToolTip(self.tr("Read installed apps and supported settings on this computer"))
        self.refresh_button.clicked.connect(self.refreshRequested.emit)
        top.addWidget(self.refresh_button)
        self.import_button = QPushButton(self.tr("Import JSON…"))
        self.import_button.setAccessibleName(self.tr("Import JSON configuration"))
        self.import_button.clicked.connect(self._import_file)
        top.addWidget(self.import_button)
        self.sources_button = QPushButton(self.tr("Sources"))
        self.sources_button.setAccessibleName(self.tr("Review app sources"))
        self.sources_button.setToolTip(self.tr("Review app sources"))
        self.sources_button.clicked.connect(lambda: self.routeRequested.emit("software:repos", {}))
        top.addWidget(self.sources_button)
        top.addStretch(1)
        root.addLayout(top)
        self.status = QLabel(self.tr("Read the computer before creating or comparing a configuration."))
        self.status.setWordWrap(True)
        self.status.setObjectName("setupConfigurationStatus")
        root.addWidget(self.status)

        self.setup_picker = QComboBox()
        self.setup_picker.setAccessibleName(self.tr("Saved Fedora configurations"))
        self.setup_picker.currentIndexChanged.connect(self._setup_changed)
        root.addWidget(self.setup_picker)
        self.progress_status = QLabel()
        self.progress_status.setWordWrap(True)
        self.progress_status.setObjectName("setupProgressStatus")
        root.addWidget(self.progress_status)

        actions = QHBoxLayout()
        self.compare_button = QPushButton(self.tr("Compare"))
        self.compare_button.setAccessibleName(self.tr("Compare with this computer"))
        self.compare_button.setToolTip(self.tr("Compare with this computer"))
        self.compare_button.clicked.connect(self._compare)
        actions.addWidget(self.compare_button)
        self.apply_button = QPushButton(self.tr("Review setup"))
        self.apply_button.setAccessibleName(self.tr("Review and apply"))
        self.apply_button.setToolTip(self.tr("Review and apply"))
        self.apply_button.clicked.connect(self._apply)
        actions.addWidget(self.apply_button)
        self.export_button = QPushButton(self.tr("Export"))
        self.export_button.setAccessibleName(self.tr("Export JSON configuration"))
        self.export_button.setToolTip(self.tr("Export JSON configuration"))
        self.export_button.clicked.connect(self._export_file)
        actions.addWidget(self.export_button)
        self.remove_button = QPushButton(self.tr("Remove"))
        self.remove_button.setAccessibleName(self.tr("Remove saved setup"))
        self.remove_button.setToolTip(self.tr("Remove saved setup"))
        self.remove_button.clicked.connect(self._remove)
        actions.addWidget(self.remove_button)
        actions.addStretch(1)
        root.addLayout(actions)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self.app_search = QLineEdit()
        self.app_search.setPlaceholderText(self.tr("Filter installed desktop apps…"))
        self.app_search.setAccessibleName(self.tr("Filter installed apps"))
        self.app_model, self.app_proxy, self.app_table = self._make_table((self.tr("Include"), self.tr("App"), self.tr("Source"), self.tr("Installation")))
        app_tab = QWidget()
        app_layout = QVBoxLayout(app_tab)
        app_layout.addWidget(self.app_search)
        app_layout.addWidget(self.app_table)
        self.tabs.addTab(app_tab, self.tr("Applications"))
        self.setting_search = QLineEdit()
        self.setting_search.setPlaceholderText(self.tr("Filter supported settings…"))
        self.setting_search.setAccessibleName(self.tr("Filter supported settings"))
        self.settings_model, self.settings_proxy, self.settings_table = self._make_table((self.tr("Include"), self.tr("Setting"), self.tr("Current value")))
        settings_tab = QWidget()
        settings_layout = QVBoxLayout(settings_tab)
        settings_layout.addWidget(self.setting_search)
        settings_layout.addWidget(self.settings_table)
        self.tabs.addTab(settings_tab, self.tr("Settings"))
        self.app_search.textChanged.connect(self.app_proxy.setFilterFixedString)
        self.setting_search.textChanged.connect(self.settings_proxy.setFilterFixedString)

        create = QHBoxLayout()
        self.setup_name = QLineEdit()
        self.setup_name.setPlaceholderText(self.tr("For example: Work or Creative"))
        self.setup_name.setAccessibleName(self.tr("Configuration name"))
        create.addWidget(self.setup_name, 1)
        self.create_button = QPushButton(self.tr("Save selected items"))
        self.create_button.clicked.connect(self._create)
        create.addWidget(self.create_button)
        root.addLayout(create)
        self._inventory = InstalledInventory()
        self._states: dict[str, TweakState] = {}
        self._documents: dict[str, SetupDocument] = {}
        self._selected_setup_id = ""
        self._pending_profile: TweakProfile | None = None
        self._pending_app: SetupApplication | None = None
        self._desktop_id = ""
        self._progress_records: tuple[dict[str, Any], ...] = ()
        self._active_progress_id = ""
        self._active_document_id = ""
        self._active_profile: TweakProfile | None = None
        self.main_window: QWidget | None = parent
        self._dialogs: list[QDialog] = []
        self.reload_setup_library()

    def reload_setup_library(self) -> None:
        try:
            self.set_setups(SetupLibrary().list())
        except (OSError, ValueError) as exc:
            self.set_setups(())
            self.set_status(self.tr("The local configuration library could not be read. It was left unchanged. %1")
                            .replace("%1", str(exc)))

    def _make_table(self, headers: tuple[str, ...]):
        model = QStandardItemModel(self)
        model.setHorizontalHeaderLabels(headers)
        proxy = QSortFilterProxyModel(self)
        proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        proxy.setFilterKeyColumn(-1)
        proxy.setSourceModel(model)
        table = QTableView()
        table.setModel(proxy)
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(True)
        table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        vertical_header = table.verticalHeader()
        if vertical_header is not None:
            vertical_header.setVisible(False)
        header = table.horizontalHeader()
        if header is not None:
            header.setStretchLastSection(False)
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            for column in range(2, model.columnCount()):
                header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        table.setSortingEnabled(True)
        table.sortByColumn(1, Qt.SortOrder.AscendingOrder)
        table.setAccessibleName(headers[1] if len(headers) > 1 else self.tr("Setup items"))
        return model, proxy, table

    def _navigate(self, route: str):
        self.routeRequested.emit(route, {})

    def _import_file(self):
        filename, _filter = QFileDialog.getOpenFileName(self, self.tr("Import configuration"), "", self.tr("JSON files (*.json)"))
        if not filename:
            return
        try:
            path = Path(filename)
            with path.open("rb") as stream:
                payload = stream.read(256 * 1024 + 1)
            if len(payload) > 256 * 1024:
                raise ValueError("Configuration file exceeds the size limit.")
            document = parse_setup(payload)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, self.tr("Cannot import configuration"), str(exc))
            return
        if self._show_import_preview(document):
            self.importRequested.emit(document)

    def _show_import_preview(self, document: SetupDocument) -> bool:
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("Review imported configuration"))
        dialog.setAccessibleName(self.tr("Configuration import preview"))
        dialog.resize(760, 560)
        layout = QVBoxLayout(dialog)
        heading = QLabel(self.tr("%1 · %2 apps · %3 settings")
                         .replace("%1", document.name)
                         .replace("%2", str(len(document.applications)))
                         .replace("%3", str(len(document.profile.settings))))
        heading.setWordWrap(True)
        layout.addWidget(heading)
        note = QLabel(self.tr("Importing adds this data to the local Loofi library. No applications or settings will change."))
        note.setWordWrap(True)
        layout.addWidget(note)
        table = QTableView(dialog)
        table.setAccessibleName(self.tr("Imported application and setting values"))
        model = QStandardItemModel(dialog)
        model.setHorizontalHeaderLabels((self.tr("Kind"), self.tr("Item"), self.tr("Source or desktop"), self.tr("Saved target")))
        for app in document.applications:
            scope = app.installation
            hint = f"{app.source_hint} · {scope}" if app.source_hint else scope
            model.appendRow([QStandardItem(self.tr("Application")), QStandardItem(app.name or app.app_id),
                             QStandardItem(app.source.upper() + " · " + hint), QStandardItem(app.ref)])
        for identifier, value in document.profile.settings:
            model.appendRow([QStandardItem(self.tr("Setting")), QStandardItem(identifier),
                             QStandardItem(document.profile.desktop.upper()), QStandardItem(value)])
        table.setModel(model)
        table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        header = table.horizontalHeader()
        if header is not None:
            header.setStretchLastSection(True)
        layout.addWidget(table, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        accept = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if accept is not None:
            accept.setText(self.tr("Import to local library"))
            accept.setAutoDefault(False)
        cancel = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel is not None:
            cancel.setDefault(True)
            cancel.setAutoDefault(False)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        return dialog.exec() == QDialog.DialogCode.Accepted

    def _export_file(self):
        setup_id = self._selected_setup_id
        document = self._documents.get(setup_id)
        if document is None:
            return
        filename, _filter = QFileDialog.getSaveFileName(self, self.tr("Export configuration"), f"{document.name}.json", self.tr("JSON files (*.json)"))
        if not filename:
            return
        from core.state.atomic_io import atomic_write_bytes
        try:
            atomic_write_bytes(Path(filename), serialize_setup(document), keep_backup=False)
        except OSError as exc:
            QMessageBox.warning(self, self.tr("Export failed"), str(exc))
            return
        self.set_status(self.tr("Configuration exported. The file contains only selected app intents and settings."))

    def _remove(self):
        if not self._selected_setup_id:
            return
        if QMessageBox.question(self, self.tr("Remove saved setup"), self.tr("Remove this configuration from the local library?")) != QMessageBox.StandardButton.Yes:
            return
        from core.tasks.setup_configurations import SetupLibrary
        try:
            SetupLibrary().remove(self._selected_setup_id)
            self.set_setups(SetupLibrary().list())
            self.set_status(self.tr("Saved configuration removed."))
        except (OSError, ValueError) as exc:
            self.set_status(str(exc))

    def _compare(self):
        if self._selected_setup_id:
            self.compareRequested.emit(self._selected_setup_id)

    def _apply(self):
        if self._selected_setup_id:
            self.applyRequested.emit(self._selected_setup_id)

    def _create(self):
        name = self.setup_name.text().strip()
        if not name:
            self.set_status(self.tr("Enter a name before saving this configuration."))
            return
        if not self._states and self._pending_profile is None and self._pending_app is None:
            self.set_status(self.tr("Read the computer before selecting configuration items."))
            return
        applications = self.selected_applications()
        if len(applications) > 200:
            self.set_status(self.tr("Choose 200 applications or fewer."))
            return
        if self._pending_profile is not None:
            profile = TweakProfile(name, self._pending_profile.desktop, self._pending_profile.settings)
        else:
            selected_ids = self.selected_setting_ids()
            settings = tuple((identifier, self._states[identifier].value) for identifier in selected_ids
                             if identifier in self._states and self._states[identifier].status == "ready")
            profile = TweakProfile(name, self._desktop(), settings)
        if not applications and not profile.settings:
            self.set_status(self.tr("Select at least one application or supported setting."))
            return
        document = SetupDocument(name, applications, profile)
        self._pending_profile = None
        self.importRequested.emit(document)

    def selected_applications(self) -> tuple[SetupApplication, ...]:
        values = []
        for row in range(self.app_model.rowCount()):
            if self.app_model.item(row, 0).checkState() == Qt.CheckState.Checked:
                app = self.app_model.item(row, 0).data(Qt.ItemDataRole.UserRole)
                if isinstance(app, SetupApplication):
                    values.append(app)
        if self._pending_app is not None:
            if all(app.identity != self._pending_app.identity for app in values):
                values.append(self._pending_app)
            self._pending_app = None
        return tuple(values)

    def selected_setting_ids(self) -> tuple[str, ...]:
        return tuple(self.settings_model.item(row, 0).data(Qt.ItemDataRole.UserRole)
                     for row in range(self.settings_model.rowCount())
                     if self.settings_model.item(row, 0).checkState() == Qt.CheckState.Checked)

    def _desktop(self) -> str:
        return str(self._desktop_id)

    def set_platform_profile(self, profile: object) -> None:
        self.platform_profile = profile
        from core.tasks.tweaks import _profile_desktop
        self._desktop_id = _profile_desktop(profile)

    def set_inventory(self, inventory: InstalledInventory, states: tuple[TweakState, ...]) -> None:
        self._inventory = inventory
        previous_apps = {self.app_model.item(row, 0).data(Qt.ItemDataRole.UserRole).identity
                         for row in range(self.app_model.rowCount())
                         if self.app_model.item(row, 0).checkState() == Qt.CheckState.Checked}
        previous_settings = {self.settings_model.item(row, 0).data(Qt.ItemDataRole.UserRole)
                             for row in range(self.settings_model.rowCount())
                             if self.settings_model.item(row, 0).checkState() == Qt.CheckState.Checked}
        self.app_model.removeRows(0, self.app_model.rowCount())
        for installed in inventory.applications:
            try:
                intent = setup_app_from_installed(installed)
            except ValueError:
                continue
            include = QStandardItem()
            include.setCheckable(True)
            include.setCheckState(Qt.CheckState.Checked if intent.identity in previous_apps else Qt.CheckState.Unchecked)
            include.setData(intent, Qt.ItemDataRole.UserRole)
            source = "RPM" if intent.source == "fedora" else "Flatpak"
            row = (include, QStandardItem(installed.name), QStandardItem(source), QStandardItem(installed.installation))
            self.app_model.appendRow(list(row))
        self._states = {state.tweak.id: state for state in states}
        self.settings_model.removeRows(0, self.settings_model.rowCount())
        for state in states:
            if state.status != "ready" or state.tweak.system_wide or state.tweak.privileged:
                continue
            include = QStandardItem()
            include.setCheckable(True)
            include.setCheckState(Qt.CheckState.Checked if state.tweak.id in previous_settings else Qt.CheckState.Unchecked)
            include.setData(state.tweak.id, Qt.ItemDataRole.UserRole)
            self.settings_model.appendRow([include, QStandardItem(state.tweak.title), QStandardItem(state.value)])
        app_details = self.tr("%1 apps read.").replace("%1", str(len(inventory.applications)))
        if inventory.errors:
            app_details += " " + self.tr("Some sources are unknown; comparisons may be incomplete.")
        self.set_status(app_details + " " + self.tr("Choose items to save, or select a setup to compare."))
        self._refresh_progress_status()

    def set_setups(self, setups: tuple[tuple[str, SetupDocument], ...]) -> None:
        previous = self._selected_setup_id
        self._documents = dict(setups)
        self.setup_picker.blockSignals(True)
        self.setup_picker.clear()
        self.setup_picker.addItem(self.tr("Choose a saved configuration"), "")
        for identifier, document in setups:
            self.setup_picker.addItem(document.name, identifier)
        index = self.setup_picker.findData(previous)
        self.setup_picker.setCurrentIndex(index if index >= 0 else 0)
        self.setup_picker.blockSignals(False)
        self._setup_changed()
        self._refresh_progress_status()

    def _setup_changed(self, _index: int = -1) -> None:
        self._selected_setup_id = str(self.setup_picker.currentData() or "")
        selected = bool(self._selected_setup_id)
        self.compare_button.setEnabled(selected)
        self.apply_button.setEnabled(selected)
        self.export_button.setEnabled(selected)
        self.remove_button.setEnabled(selected)
        self._refresh_progress_status()

    def _refresh_progress_status(self) -> None:
        try:
            self._progress_records = SetupProgressStore().list()
        except (OSError, ValueError) as exc:
            self.progress_status.setText(self.tr("Saved setup progress is unavailable: %1").replace("%1", str(exc)))
            return
        records = [record for record in self._progress_records if record.get("setup_id") == self._selected_setup_id]
        if not records:
            self.progress_status.setText(self.tr("No saved application steps for this configuration."))
            return
        latest = max(records, key=lambda record: float(record.get("started_at", 0)))
        counts: dict[str, int] = {}
        for state in latest.get("steps", {}).values():
            status = str(state.get("status", "not_started"))
            counts[status] = counts.get(status, 0) + 1
        summary = ", ".join(f"{count} {status.replace('_', ' ')}" for status, count in sorted(counts.items()))
        self.progress_status.setText(self.tr("Previous review %1: %2. Compare with this computer before starting a new review.")
                                     .replace("%1", str(latest.get("status", "unknown")))
                                     .replace("%2", summary))

    def show_comparison(self, comparison: object) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("Configuration comparison"))
        dialog.setAccessibleName(self.tr("Read-only comparison with this computer"))
        dialog.resize(760, 520)
        layout = QVBoxLayout(dialog)
        stamp = getattr(comparison, "sampled_at", 0)
        timestamp = QLabel(self.tr("Read at %1").replace("%1", datetime.fromtimestamp(stamp).astimezone().strftime("%Y-%m-%d %H:%M") if stamp else self.tr("Time unavailable")))
        layout.addWidget(timestamp)
        table = QTableView(dialog)
        model = QStandardItemModel(dialog)
        model.setHorizontalHeaderLabels((self.tr("Type"), self.tr("Item"), self.tr("Status"), self.tr("Current"), self.tr("Target"), self.tr("Details")))
        for entry in getattr(comparison, "entries", ()):
            model.appendRow([QStandardItem(str(getattr(entry, key, ""))) for key in ("kind", "title", "status", "current", "desired", "message")])
        table.setModel(model)
        table.setSortingEnabled(True)
        layout.addWidget(table)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        self._dialogs.append(dialog)
        dialog.finished.connect(lambda _result: self._dialogs.remove(dialog) if dialog in self._dialogs else None)
        dialog.exec()
        if dialog in self._dialogs:
            self._dialogs.remove(dialog)

    def begin_progress(self, progress_id: str, document_id: str, profile: TweakProfile | None = None) -> None:
        self._active_progress_id = progress_id
        self._active_document_id = document_id
        self._active_profile = profile

    def record_skipped_steps(self, progress_id: str, steps: tuple[str, ...], message: str) -> bool:
        """Persist explicit skips before any remaining setup step can mutate the host."""
        try:
            store = SetupProgressStore()
            for step in steps:
                store.update(progress_id, step, "skipped")
        except (OSError, ValueError) as exc:
            self.set_status(self.tr("An explicitly skipped step could not be saved. No setup changes were started. %1")
                            .replace("%1", str(exc)))
            self._refresh_progress_status()
            return False
        self.set_status(message)
        self._refresh_progress_status()
        return True

    def on_application_review_started(self, item: Any) -> bool:
        if not self._active_progress_id:
            return True
        from core.tasks.setup_configurations import SetupProgressStore
        try:
            SetupProgressStore().update(self._active_progress_id, f"app:{item.item_id}", "running")
        except (OSError, ValueError):
            self.set_status(self.tr("Progress could not be saved. Recheck installed apps before continuing."))
            return False
        return True

    def on_application_review_stopped(self, item: Any, status: str) -> None:
        if not self._active_progress_id:
            return
        try:
            SetupProgressStore().update(self._active_progress_id, f"app:{item.item_id}", status)
        except (OSError, ValueError):
            self.set_status(self.tr("The stopped review could not be saved in setup progress."))

    def on_setup_action_prepared(self, ticket: Any) -> bool:
        state = getattr(self.main_window, "_application_review_state", None)
        item = state.get("current") if isinstance(state, dict) else None
        if item is None or not self._active_progress_id:
            return True
        try:
            SetupProgressStore().update(self._active_progress_id, f"app:{item.item_id}", "running", plan_id=str(ticket.plan.plan_id))
        except (OSError, ValueError):
            self.set_status(self.tr("The exact review could not be linked to saved setup progress."))
            return False
        return True

    def on_application_item_finished(self, item: Any, outcome: Any) -> bool:
        if not self._active_progress_id:
            return True
        status = "succeeded" if bool(getattr(outcome, "success", False)) else "failed"
        try:
            SetupProgressStore().update(self._active_progress_id, f"app:{item.item_id}", status,
                                        plan_id=str(getattr(outcome, "plan_id", "")),
                                        action_run_id=str(getattr(outcome, "run_id", "")))
        except (OSError, ValueError):
            self.set_status(self.tr("The application result remains in Activity; setup progress could not be updated."))
            return False
        if status != "succeeded":
            self.set_status(self.tr("Application setup stopped after a failed step. Compare again before requesting a new review."))
        return status == "succeeded"

    def set_results(self, outcome: object) -> None:
        if not self._active_progress_id:
            return
        successful = str(getattr(outcome, "status", "")) == "succeeded"
        results = tuple(getattr(outcome, "results", ()))
        for item in results:
            if bool(getattr(item, "skipped", False)):
                continue
            status = "succeeded" if bool(getattr(item, "success", False)) else "failed"
            try:
                SetupProgressStore().update(self._active_progress_id, f"app:{item.item_id}", status,
                                            plan_id=str(getattr(item, "plan_id", "")),
                                            action_run_id=str(getattr(item, "run_id", "")))
            except (OSError, ValueError):
                successful = False
        if not successful:
            self.set_status(self.tr("Application setup stopped. Compare again before reviewing the remaining steps."))
            self._refresh_progress_status()
            return
        try:
            active_run = next((record for record in SetupProgressStore().list()
                               if record.get("id") == self._active_progress_id), None)
        except (OSError, ValueError) as exc:
            self.set_status(self.tr("Saved setup progress could not be checked, so later settings were not started. %1")
                            .replace("%1", str(exc)))
            return
        if active_run is not None and any(step.startswith("app:") and state.get("status") in {"not_started", "running"}
                                          for step, state in active_run.get("steps", {}).items()):
            self.set_status(self.tr("This app review batch is verified. Rechecking the remaining apps before desktop settings."))
            self._refresh_progress_status()
            self.continueSetupRequested.emit(self._active_document_id, self._active_progress_id)
            return
        try:
            document = SetupLibrary().get(self._active_document_id)
        except (OSError, ValueError) as exc:
            self.set_status(self.tr("The saved configuration could not be read, so later settings were not started. %1")
                            .replace("%1", str(exc)))
            return
        profile = self._active_profile or document.profile
        if profile.settings:
            self.profileReviewRequested.emit(self._active_progress_id, profile)
        else:
            skipped = any(state.get("status") == "skipped" for state in active_run.get("steps", {}).values()) if active_run else False
            self.set_status(self.tr("Selected applications are verified; some steps were explicitly skipped.") if skipped
                            else self.tr("Selected applications are verified. This configuration has no desktop settings."))
        self._refresh_progress_status()

    def set_status(self, message: str) -> None:
        self.status.setText(str(message))

    def set_profile_notice(self, message: str, error: bool = False) -> None:
        self.set_status(message)

    def set_pending_application(self, payload: object) -> None:
        if isinstance(payload, dict) and set(payload) == {"name", "app_id", "source", "installation", "ref", "version", "size"}:
            if any(not isinstance(value, str) for value in payload.values()):
                self.set_status(self.tr("The selected application could not be added."))
                return
            try:
                installed = InstalledApplication(**payload)
                self._pending_app = setup_app_from_installed(installed)
                self.setup_name.setFocus()
                self.set_status(self.tr("Selected %1. Choose any settings and save it in a named configuration.").replace("%1", installed.name))
            except (TypeError, ValueError):
                self.set_status(self.tr("The selected application could not be added."))

    def set_pending_profile(self, profile: TweakProfile) -> None:
        self._pending_profile = profile
        self.setup_name.setText(profile.name)
        self.set_status(self.tr("Selected settings profile %1. Add apps if you want, then save the configuration.").replace("%1", profile.name))

    def finish_profile(self, result: object) -> None:
        if not self._active_progress_id:
            return
        entries = tuple(getattr(result, "entries", ()))
        failed = False
        for item in entries:
            status = ("succeeded" if item.status == "succeeded" else "skipped" if item.status == "skipped"
                      else "unavailable" if item.status == "unavailable" else "interrupted" if item.status == "interrupted" else "failed")
            failed = failed or status in {"failed", "unavailable", "interrupted"}
            try:
                plan_id = ""
                run_id = str(getattr(item, "run_id", ""))
                if run_id:
                    from core.actions.stores import ActionRunStore
                    action_run = ActionRunStore().get(run_id)
                    plan_id = str(getattr(action_run, "plan_id", "")) if action_run is not None else ""
                SetupProgressStore().update(self._active_progress_id, f"setting:{item.id}", status,
                                            plan_id=plan_id, action_run_id=run_id)
            except (OSError, ValueError):
                failed = True
        skipped = any(getattr(item, "status", "") == "skipped" for item in entries)
        self.set_status(self.tr("Settings finished with a failure. Compare again before continuing.") if failed
                        else self.tr("Some settings were explicitly skipped. Compare again to verify the current computer.") if skipped
                        else self.tr("Configuration steps finished. Compare again to verify the current computer."))
        self._refresh_progress_status()

    def skip_profile_step(self, progress_id: str, profile: TweakProfile) -> None:
        for identifier, _value in profile.settings:
            try:
                SetupProgressStore().update(progress_id, f"setting:{identifier}", "skipped")
            except (OSError, ValueError):
                self.set_status(self.tr("Skipped settings could not be saved in setup progress."))
                break
        self.set_status(self.tr("Desktop settings were explicitly skipped. Compare again to check this computer."))
        self._refresh_progress_status()

    def record_profile_review_stopped(self, progress_id: str, profile: TweakProfile, status: str, message: str) -> None:
        for identifier, _value in profile.settings:
            try:
                SetupProgressStore().update(progress_id, f"setting:{identifier}", status)
            except (OSError, ValueError) as exc:
                self.set_status(self.tr("The stopped setting review could not be saved. %1").replace("%1", str(exc)))
                self._refresh_progress_status()
                return
        self.set_status(message)
        self._refresh_progress_status()

    def finish_setup_without_apps(self) -> None:
        if not self._active_progress_id:
            return
        document = SetupLibrary().get(self._active_document_id)
        profile = self._active_profile or document.profile
        if profile.settings:
            self.profileReviewRequested.emit(self._active_progress_id, profile)
        else:
            skipped = False
            try:
                record = next((item for item in SetupProgressStore().list() if item.get("id") == self._active_progress_id), None)
                skipped = bool(record and any(state.get("status") == "skipped" for state in record.get("steps", {}).values()))
            except (OSError, ValueError):
                pass
            self.set_status(self.tr("Some unavailable steps were explicitly skipped. Compare again to verify the computer.")
                            if skipped else self.tr("This configuration is already satisfied."))
        self._refresh_progress_status()

    def cleanup(self, timeout_ms: int = 1000) -> bool:
        del timeout_ms
        return True


class SetupConfigurationsPlugin(PluginInterface):
    """Hidden Overview child route discovered by global search and task cards."""

    def __init__(self):
        self._context: dict[str, Any] = {}
        self._widget: SetupConfigurationsPage | None = None

    def metadata(self) -> PluginMetadata:
        return plugin_metadata_for_module(__name__)

    def set_context(self, context: dict) -> None:
        self._context = dict(context)

    def create_widget(self) -> QWidget:
        if self._widget is None:
            main = self._context.get("main_window")
            self._widget = SetupConfigurationsPage(main)
            self._widget.main_window = main
            if main is not None:
                self._widget.set_platform_profile(getattr(main, "_platform_profile", None))
        return self._widget
