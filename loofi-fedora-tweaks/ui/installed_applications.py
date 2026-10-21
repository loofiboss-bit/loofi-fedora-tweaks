"""Installed app presentation; operations are handed to the shared controller."""
from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QApplication, QComboBox, QDialog, QDialogButtonBox, QLabel, QMenu, QPushButton, QLayout, QToolButton, QVBoxLayout

from core.catalog_models import NativeHandoffId
from services.software.app_comparison import compare_installations, comparison_id
from services.software.installed_applications import InstalledApplication, InstalledInventory, filter_installed_applications
from ui.components import Card, DetailsDisclosure
from ui.operation_worker import OperationControllerQtAdapter
from ui.native_handoff_card import ManagedNativeHandoffCard


class FlatpakPermissionsDialog(QDialog):
    """Readable, read-only view of one installation's app metadata grants."""

    def __init__(self, app: InstalledApplication, permissions: object, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Flatpak permissions"))
        self.setAccessibleName(self.tr("Flatpak permissions for %1").replace("%1", app.name))
        self.resize(760, 560)
        layout = QVBoxLayout(self)
        identity = QLabel(
            self.tr("%1\nRef: %2\nInstallation: %3")
            .replace("%1", app.name).replace("%2", app.ref).replace("%3", app.installation)
        )
        identity.setWordWrap(True)
        layout.addWidget(identity)
        permission_notice = QLabel(self.tr(
            "These permissions come from the app metadata. User overrides and desktop portals can change actual access."
        ))
        permission_notice.setWordWrap(True)
        layout.addWidget(permission_notice)

        grouped: dict[str, list[str]] = {}
        friendly: list[str] = []
        for permission in getattr(permissions, "permissions", ()):
            category = str(permission.category).strip()
            key = str(permission.key).strip()
            value = str(permission.value).strip()
            group, detail = self._describe(category, key, value)
            plain_description = self._plain_language(category, key, value)
            if plain_description and plain_description not in friendly:
                friendly.append(plain_description)
            shown_value = self.tr("Value hidden for privacy") if category.lower() == "environment" else value
            line = self.tr("%1: %2").replace("%1", key).replace("%2", shown_value)
            if detail:
                line += self.tr(" — %1").replace("%1", detail)
            if group == self.tr("Technical details"):
                line = self.tr("%1 / %2: %3").replace("%1", category).replace("%2", key).replace("%3", shown_value)
            grouped.setdefault(group, []).append(line)

        if grouped:
            blocks = [f"{group}\n" + "\n".join(f"  {line}" for line in entries)
                      for group, entries in grouped.items()]
            exact = "\n\n".join(blocks)
        else:
            exact = self.tr("No permissions were reported by the app metadata.")
        if friendly:
            summary = QLabel("\n".join(f"• {item}" for item in friendly))
            summary.setObjectName("flatpakPermissionSummary")
            summary.setWordWrap(True)
            summary.setAccessibleName(self.tr("Plain-language permission summary"))
            layout.addWidget(summary)
        disclosure = DetailsDisclosure(exact, summary=self.tr("Show exact permission metadata"))
        disclosure.setAccessibleName(self.tr("Exact Flatpak permission metadata"))
        layout.addWidget(disclosure, 1)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        close.accepted.connect(self.accept)
        layout.addWidget(close)

    def _describe(self, category: str, key: str, value: str) -> tuple[str, str]:
        normalized_category = category.lower()
        normalized_key = key.lower()
        if "bus" in normalized_category:
            return self.tr("D-Bus"), self.tr("Access to named desktop services")
        if normalized_category == "environment":
            return self.tr("Environment"), self.tr("Values are hidden for privacy")
        if normalized_category == "context":
            if normalized_key == "filesystems":
                if value.startswith("!"):
                    return self.tr("Files"), self.tr("Access denied")
                mode = self.tr("read-only") if value.endswith(":ro") else self.tr("read/write")
                return self.tr("Files"), mode
            if normalized_key == "shared" and value == "network":
                return self.tr("Network"), self.tr("Network access")
            if normalized_key == "sockets" and value in {"pulseaudio", "pipewire", "alsa"}:
                return self.tr("Audio"), self.tr("Audio service access")
            if normalized_key == "sockets" and value in {"wayland", "x11", "fallback-x11"}:
                return self.tr("Display"), self.tr("Display server access")
            if normalized_key == "devices":
                return self.tr("Devices"), self.tr("Device access")
            if normalized_key in {"sockets", "shared", "features", "filesystems"}:
                return self.tr("Desktop and system access"), ""
        return self.tr("Technical details"), ""

    def _plain_language(self, category: str, key: str, value: str) -> str:
        """Explain a small closed set of known Flatpak grants without guessing."""
        if category.lower() != "context":
            return ""
        normalized_key = key.lower()
        if normalized_key == "shared" and value == "network":
            return self.tr("Can connect to the network.")
        if normalized_key == "sockets" and value in {"wayland", "x11", "fallback-x11"}:
            return self.tr("Can display windows in your desktop session.")
        if normalized_key == "sockets" and value in {"pulseaudio", "pipewire", "alsa"}:
            return self.tr("Can use audio services.")
        if normalized_key == "filesystems":
            target, separator, mode = value.partition(":")
            if target == "home":
                access = self.tr("read-only") if separator and mode == "ro" else self.tr("read and write")
                return self.tr("Has %1 access to your home folder.").replace("%1", access)
            known_folders = {"xdg-download": "Downloads", "xdg-documents": "Documents", "xdg-pictures": "Pictures", "xdg-videos": "Videos", "xdg-music": "Music"}
            if target in known_folders:
                access = self.tr("read-only") if separator and mode == "ro" else self.tr("read and write")
                return self.tr("Has %1 access to %2.").replace("%1", access).replace("%2", self.tr(known_folders[target]))
        return ""


class _InstalledApplicationRow(Card):
    """Keep wrapped identity text readable inside the scrolling inventory."""

    def __init__(self, title, description):
        super().__init__(title, description)
        self.body.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        for label in (self.title_label, self.description_label):
            label.setMinimumHeight(max(1, label.heightForWidth(max(1, label.width()))))


class InstalledApplicationsCard(Card):
    actionReviewRequested = pyqtSignal(str, object)
    nativeSettingsRequested = pyqtSignal(object)
    routeRequested = pyqtSignal(str, object)
    inventoryUpdated = pyqtSignal(object)
    stopped = pyqtSignal()

    def __init__(self, *, service=None, parent=None):
        super().__init__(self.tr("Installed"), self.tr("Installed Flatpaks and RPM applications with visible desktop entries, plus curated RPM applications."))
        self.service = service
        self.inventory = InstalledInventory(unknown_sources=frozenset({"flatpak", "fedora"}))
        self.refresh_button = QPushButton(self.tr("Refresh installed applications"))
        self.refresh_button.clicked.connect(self.refresh)
        self.add_widget(self.refresh_button)
        self.status = QLabel(self.tr("Installation status has not been checked."))
        self.status.setWordWrap(True)
        self.add_widget(self.status)
        self.search_summary = QLabel()
        self.search_summary.setObjectName("installedSearchSummary")
        self.search_summary.setWordWrap(True)
        self.add_widget(self.search_summary)
        self.software_handoff = ManagedNativeHandoffCard(NativeHandoffId.SOFTWARE_CENTER, title=self.tr("Manage RPM applications"), description=self.tr("Review RPM removal in your desktop software manager."), button_text=self.tr("Open software manager"), parent=self)
        self.software_handoff.hide()
        self.add_widget(self.software_handoff)
        self.software_package = QLabel()
        self.software_package.setObjectName("softwareManagerPackage")
        self.software_package.setWordWrap(True)
        self.software_package.hide()
        self.software_handoff.layout().addWidget(self.software_package)
        self.copy_package_button = QPushButton(self.tr("Copy package name"))
        self.copy_package_button.setObjectName("copySoftwareManagerPackage")
        self.copy_package_button.clicked.connect(self.copy_software_manager_package)
        self.copy_package_button.hide()
        self.software_handoff.layout().addWidget(self.copy_package_button)
        self._software_manager_app = None
        self.source_filter = QComboBox()
        self.source_filter.setAccessibleName(self.tr("Installed application source"))
        self.source_filter.addItem(self.tr("All sources"), "")
        self.source_filter.addItem(self.tr("Flatpak"), "flatpak")
        self.source_filter.addItem(self.tr("RPM"), "fedora")
        self.installation_filter = QComboBox()
        self.installation_filter.setAccessibleName(self.tr("Installed application installation"))
        self.installation_filter.addItem(self.tr("All installations"), "")
        self.sort_order = QComboBox()
        self.sort_order.setAccessibleName(self.tr("Sort installed applications"))
        self.sort_order.addItem(self.tr("Name"), "name")
        self.sort_order.addItem(self.tr("Largest reported size"), "size")
        for control in (self.source_filter, self.installation_filter, self.sort_order):
            control.currentIndexChanged.connect(self._apply_search)
            self.add_widget(control)
        size_notice = QLabel(self.tr("Reported installation sizes include shared Flatpak objects and do not predict space freed by removal. Unknown sizes are listed last."))
        size_notice.setWordWrap(True)
        self.add_widget(size_notice)
        self._comparison_dialogs = []
        self._rows = []
        self._application_rows: list[tuple[InstalledApplication, _InstalledApplicationRow]] = []
        self._search_query = ""
        self._permission_generation = 0
        self._active_permission_request = None
        self._pending_permission_request = None
        self._permission_dialogs = {}
        self._adapter = OperationControllerQtAdapter(parent=self)
        self._adapter.finished.connect(self.apply_inventory)
        self._adapter.failed.connect(self._failed)
        self._adapter.stopped.connect(lambda: self.refresh_button.setEnabled(self.service is not None))
        self._permissions_adapter = OperationControllerQtAdapter(parent=self)
        self._adapter.stopped.connect(self._notify_stopped)
        self._permissions_adapter.stopped.connect(self._notify_stopped)
        self._permissions_adapter.finished.connect(self._permissions_result)
        self._permissions_adapter.failed.connect(self._permissions_failed)
        self._permissions_adapter.stopped.connect(self._start_pending_permission)
        self.software_handoff.stopped.connect(self._notify_stopped)
        from ui.flatpak_insights import FlatpakInsightsCard
        self.insights = FlatpakInsightsCard(service=service, parent=self)
        self.insights.actionReviewRequested.connect(self.actionReviewRequested.emit)
        self.insights.stopped.connect(self._notify_stopped)
        self.add_widget(self.insights)
        from ui.flatpak_updates import FlatpakUpdatesCard
        self.updates = FlatpakUpdatesCard(show_updates_link=True, parent=self)
        self.updates.hide()
        self.updates.actionReviewRequested.connect(self.actionReviewRequested.emit)
        self.updates.routeRequested.connect(self.routeRequested.emit)
        self.updates.stopped.connect(self._notify_stopped)
        self.add_widget(self.updates)
        self.refresh_button.setEnabled(service is not None)

    @property
    def busy(self):
        return self._adapter.busy or self._permissions_adapter.busy or self.insights.busy or self.software_handoff.busy or self.updates.busy

    def request_stop(self):
        self._close_comparison_dialogs()
        self._permission_generation += 1
        self._pending_permission_request = None
        self._close_permission_dialogs()
        self.updates.request_stop()
        self.insights.request_stop()
        self.software_handoff.request_stop()
        self._adapter.cancel()
        self._permissions_adapter.cancel()

    def check_updates(self, app):
        if app.source != "flatpak":
            return
        self.updates.show()
        self.updates.check(app.installation, (app.ref,), auto_review=True)

    def _notify_stopped(self):
        if not self.busy:
            self.stopped.emit()

    def cleanup(self, timeout_ms=1000):
        self.request_stop()
        inventory_stopped = self._adapter.close(timeout_ms)
        permissions_stopped = self._permissions_adapter.close(timeout_ms)
        updates_stopped = self.updates.cleanup(timeout_ms)
        insights_stopped = self.insights.cleanup(timeout_ms)
        handoff_stopped = self.software_handoff.cleanup(timeout_ms)
        return updates_stopped and insights_stopped and inventory_stopped and permissions_stopped and handoff_stopped

    def open_software_manager(self, app: InstalledApplication | None = None):
        self._software_manager_app = app if app is not None and app.source == "fedora" else None
        if self._software_manager_app is not None:
            package = self._software_manager_app.ref
            self.software_handoff.description_label.setText(
                self.tr("Search for this exact RPM package in the software manager. Loofi does not open an app-specific page or remove it. Return to Apps and refresh installed applications to verify the result.")
            )
            self.software_package.setText(self.tr("Package name: %1").replace("%1", package))
            self.software_package.show()
            self.copy_package_button.show()
        else:
            self.software_handoff.description_label.setText(self.tr("Review RPM removal in your desktop software manager."))
            self.software_package.hide()
            self.copy_package_button.hide()
        self.software_handoff.show()
        if self.software_handoff.open_button.isEnabled():
            self.software_handoff.open_button.click()

    def copy_software_manager_package(self):
        app = self._software_manager_app
        if app is None or app.source != "fedora":
            return
        QApplication.clipboard().setText(app.ref)
        self.software_package.setText(
            self.tr("Package name copied: %1. Search for it in the software manager, then return here and refresh installed applications to verify.").replace("%1", app.ref)
        )

    def refresh(self):
        if self.service is not None and not self._adapter.busy:
            self.refresh_button.setEnabled(False)
            self.status.setText(self.tr("Checking installed applications…"))
            adapter = self._adapter
            service = self.service
            self._adapter.start(
                lambda adapter=adapter, service=service: service.snapshot(
                    cancelled=lambda adapter=adapter: adapter.cancel_requested
                )
            )

    def _failed(self, _message):
        self.apply_inventory(InstalledInventory(errors=(self.tr("Installation status could not be checked."),), unknown_sources=frozenset({"flatpak", "fedora"})))

    def apply_inventory(self, inventory):
        if not isinstance(inventory, InstalledInventory):
            self._failed("")
            return
        self._close_comparison_dialogs()
        self.inventory = inventory
        self.insights.set_installations(app.installation for app in inventory.applications if app.source == "flatpak")
        previous_installation = self.installation_filter.currentData()
        self.installation_filter.blockSignals(True)
        self.installation_filter.clear()
        self.installation_filter.addItem(self.tr("All installations"), "")
        for installation in sorted({app.installation for app in inventory.applications}):
            self.installation_filter.addItem(installation, installation)
        index = self.installation_filter.findData(previous_installation)
        self.installation_filter.setCurrentIndex(max(0, index))
        self.installation_filter.blockSignals(False)
        for row in self._rows:
            self.body.removeWidget(row)
            row.deleteLater()
        self._rows = []
        self._application_rows = []
        self.status.setText("\n".join(inventory.errors) if inventory.errors else self.tr("Installation inventory checked."))
        for app in inventory.applications:
            installation = self.tr("System") if app.installation == "system" else self.tr("User") if app.installation == "user" else self.tr("Named installation")
            version = app.version or self.tr("Version not reported")
            source_label = self.tr("RPM") if app.source == "fedora" else self.tr("Flatpak")
            row = _InstalledApplicationRow(app.name, self.tr("%1 · %2 installation · %3").replace("%1", version).replace("%2", installation).replace("%3", source_label))
            details = DetailsDisclosure(summary=self.tr("Show installation details"))
            details.set_details(self.tr("Application ID: %1\nReference: %2\nSource: %3\nInstallation: %4\nSize: %5").replace("%1", app.app_id).replace("%2", app.ref).replace("%3", source_label).replace("%4", app.installation).replace("%5", app.size or self.tr("Not reported")))
            row.add_widget(details)
            app_id = comparison_id(app)
            if app_id and len(compare_installations(inventory, app_id).installations) > 1:
                compare = QPushButton(self.tr("Compare installations"))
                compare.clicked.connect(lambda _checked=False, identifier=app_id: self.show_comparison(identifier))
                row.add_widget(compare)
            if app.source == "flatpak":
                update = QPushButton(self.tr("Check for updates"))
                update.setAccessibleName(self.tr("Check updates for %1 in %2").replace("%1", app.name).replace("%2", app.installation))
                update.clicked.connect(lambda _checked=False, item=app: self.check_updates(item))
                row.add_widget(update)
                information = QToolButton()
                information.setObjectName("installedAppInformation")
                information.setText(self.tr("App details and access"))
                information.setAccessibleName(self.tr("App details and access for %1").replace("%1", app.name))
                information.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
                information_menu = QMenu(information)
                information_menu.addSection(self.tr("Application details"))
                details_action = information_menu.addAction(self.tr("App details"))
                details_action.triggered.connect(lambda _checked=False, item=app: self.show_details(item))
                information_menu.addSection(self.tr("Application access"))
                access_action = information_menu.addAction(self.tr("Understand app access"))
                access_action.triggered.connect(lambda _checked=False, item=app: self.insights.show_access(item))
                permissions_action = information_menu.addAction(self.tr("Show declared permissions"))
                permissions_action.triggered.connect(lambda _checked=False, item=app: self.show_permissions(item))
                information.setMenu(information_menu)
                row.add_widget(information)
                remove = QPushButton(self.tr("Review removal"))
                remove.clicked.connect(lambda _checked=False, item=app: self.actionReviewRequested.emit("remove-installed-flatpak", {"ref": item.ref, "installation": item.installation}))
            else:
                from services.system import SystemManager
                if SystemManager.is_atomic():
                    remove = QPushButton(self.tr("Open software manager"))
                    remove.clicked.connect(lambda _checked=False, item=app: self.open_software_manager(item))
                else:
                    remove = QPushButton(self.tr("Review removal"))
                    remove.clicked.connect(lambda _checked=False, item=app: self.actionReviewRequested.emit("remove-application", {"source": "fedora", "package_id": item.ref}))
            row.add_widget(remove)
            self.add_widget(row)
            self._rows.append(row)
            self._application_rows.append((app, row))
        self._apply_search()
        self.inventoryUpdated.emit(inventory)

    def set_search(self, query: str) -> None:
        self._search_query = str(query or "").strip().casefold()
        self._apply_search()

    def _apply_search(self) -> None:
        query = self._search_query
        projected = filter_installed_applications(
            self.inventory, query=query, source=self.source_filter.currentData() or "",
            installation=self.installation_filter.currentData() or "", sort=self.sort_order.currentData() or "name",
        )
        identities = {(app.installation, app.ref) for app in projected}
        rows = {(app.installation, app.ref): row for app, row in self._application_rows}
        for app, row in self._application_rows:
            row.setVisible((app.installation, app.ref) in identities)
        for app in projected:
            row = rows[(app.installation, app.ref)]
            self.body.removeWidget(row)
            self.body.addWidget(row)
        matches = len(projected)
        if self.inventory.errors:
            self.search_summary.setText(self.tr("Some installation sources could not be checked. Listed applications may be incomplete."))
        elif query and matches == 0:
            self.search_summary.setText(self.tr("No installed applications match this search."))
        else:
            self.search_summary.setText(self.tr("Showing %1 of %2 installed applications.").replace("%1", str(matches)).replace("%2", str(len(self._application_rows))))

    def _close_comparison_dialogs(self):
        for dialog in tuple(self._comparison_dialogs):
            dialog.close()
        self._comparison_dialogs.clear()

    def show_comparison(self, app_id: str):
        from ui.app_comparison import ApplicationComparisonDialog
        dialog = ApplicationComparisonDialog(compare_installations(self.inventory, app_id), self)
        dialog.detailsRequested.connect(self.show_details)
        dialog.removalRequested.connect(lambda app: self.actionReviewRequested.emit("remove-installed-flatpak", {"ref": app.ref, "installation": app.installation}))
        dialog.softwareManagerRequested.connect(self.open_software_manager)
        self._comparison_dialogs.append(dialog)
        dialog.finished.connect(lambda _result: self._comparison_dialogs.remove(dialog) if dialog in self._comparison_dialogs else None)
        dialog.open()

    def show_details(self, app: InstalledApplication):
        if self.service is None or app.source != "flatpak":
            return
        self._permission_generation += 1
        self._pending_permission_request = None
        self._close_permission_dialogs()
        self._permissions_adapter.cancel()
        self.insights.show_details(app)

    def show_permissions(self, app: InstalledApplication):
        if self.service is None or app.source != "flatpak":
            return
        self.updates.request_stop()
        self.insights.request_stop()
        self._close_permission_dialogs()
        self._permission_generation += 1
        self._pending_permission_request = (app, self._permission_generation)
        if self._permissions_adapter.busy:
            self._permissions_adapter.cancel()
            self.status.setText(self.tr("Switching permission details to the selected application…"))
            return
        self._start_pending_permission()

    def _close_permission_dialogs(self):
        for dialog in tuple(self._permission_dialogs.values()):
            dialog.close()
        self._permission_dialogs.clear()

    def _permissions_result(self, permissions):
        request = self._active_permission_request
        if request is None:
            return
        app, generation = request
        if generation != self._permission_generation:
            return
        dialog = FlatpakPermissionsDialog(app, permissions, self)
        self._permission_dialogs[generation] = dialog
        dialog.finished.connect(lambda _result, key=generation: self._permission_dialogs.pop(key, None))
        dialog.open()
        self.status.setText(self.tr("Showing metadata permissions for %1.").replace("%1", app.name))

    def _permissions_failed(self, _message):
        request = self._active_permission_request
        if request is not None and request[1] == self._permission_generation:
            self.status.setText(self.tr("Permissions could not be read from this installation."))

    def _start_pending_permission(self):
        if self._permissions_adapter.busy or self._pending_permission_request is None:
            return
        app, generation = self._pending_permission_request
        self._pending_permission_request = None
        self._active_permission_request = (app, generation)
        self.status.setText(self.tr("Reading permissions for %1…").replace("%1", app.name))
        if not self._permissions_adapter.start(lambda: self.service.permissions(app)):
            self._active_permission_request = None
            self.status.setText(self.tr("Permission inspection could not be started."))
