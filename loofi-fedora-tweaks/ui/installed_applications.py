"""Installed app presentation; operations are handed to the shared controller."""
from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QPushButton, QLayout, QPlainTextEdit, QVBoxLayout

from core.catalog_models import NativeHandoffId
from services.software.installed_applications import InstalledApplication, InstalledInventory
from ui.components import Card
from ui.operation_worker import OperationControllerQtAdapter
from ui.native_handoff_card import NativeHandoffCard


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
        explanation = QLabel(self.tr(
            "These permissions come from the app metadata. User overrides and desktop portals can change actual access."
        ))
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        grouped: dict[str, list[str]] = {}
        for permission in getattr(permissions, "permissions", ()):
            category = str(permission.category).strip()
            key = str(permission.key).strip()
            value = str(permission.value).strip()
            group, detail = self._describe(category, key, value)
            shown_value = self.tr("Value hidden for privacy") if category.lower() == "environment" else value
            line = self.tr("%1: %2").replace("%1", key).replace("%2", shown_value)
            if detail:
                line += self.tr(" — %1").replace("%1", detail)
            if group == self.tr("Technical details"):
                line = self.tr("%1 / %2: %3").replace("%1", category).replace("%2", key).replace("%3", shown_value)
            grouped.setdefault(group, []).append(line)

        details = QPlainTextEdit()
        details.setReadOnly(True)
        details.setAccessibleName(self.tr("Grouped app permissions"))
        if grouped:
            blocks = [f"{group}\n" + "\n".join(f"  {line}" for line in entries)
                      for group, entries in grouped.items()]
            details.setPlainText("\n\n".join(blocks))
        else:
            details.setPlainText(self.tr("No permissions were reported by the app metadata."))
        layout.addWidget(details, 1)
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
    inventoryUpdated = pyqtSignal(object)
    stopped = pyqtSignal()

    def __init__(self, *, service=None, parent=None):
        super().__init__(self.tr("Installed"), self.tr("Installed Flatpak applications and curated Fedora RPMs."))
        self.service = service
        self.inventory = InstalledInventory(unknown_sources=frozenset({"flatpak", "fedora"}))
        self.refresh_button = QPushButton(self.tr("Refresh installed applications"))
        self.refresh_button.clicked.connect(self.refresh)
        self.add_widget(self.refresh_button)
        self.status = QLabel(self.tr("Installation status has not been checked."))
        self.status.setWordWrap(True)
        self.add_widget(self.status)
        self.software_handoff = NativeHandoffCard(NativeHandoffId.SOFTWARE_CENTER, title=self.tr("Manage Fedora RPM applications"), description=self.tr("Review RPM removal in your desktop software manager."), button_text=self.tr("Open software manager"), parent=self)
        self.software_handoff.hide()
        self.add_widget(self.software_handoff)
        self._rows = []
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
        self.refresh_button.setEnabled(service is not None)

    @property
    def busy(self):
        return self._adapter.busy or self._permissions_adapter.busy

    def request_stop(self):
        self._permission_generation += 1
        self._pending_permission_request = None
        self._close_permission_dialogs()
        self._adapter.cancel()
        self._permissions_adapter.cancel()

    def _notify_stopped(self):
        if not self.busy:
            self.stopped.emit()

    def cleanup(self, timeout_ms=1000):
        self.request_stop()
        inventory_stopped = self._adapter.close(timeout_ms)
        permissions_stopped = self._permissions_adapter.close(timeout_ms)
        return inventory_stopped and permissions_stopped

    def open_software_manager(self):
        self.software_handoff.show()
        self.software_handoff.refresh_availability()
        if self.software_handoff.open_button.isEnabled():
            self.software_handoff.open_button.click()

    def refresh(self):
        if self.service is not None and not self._adapter.busy:
            self.refresh_button.setEnabled(False)
            self.status.setText(self.tr("Checking installed applications…"))
            self._adapter.start(self.service.snapshot)

    def _failed(self, _message):
        self.apply_inventory(InstalledInventory(errors=(self.tr("Installation status could not be checked."),), unknown_sources=frozenset({"flatpak", "fedora"})))

    def apply_inventory(self, inventory):
        if not isinstance(inventory, InstalledInventory):
            self._failed("")
            return
        self.inventory = inventory
        for row in self._rows:
            self.body.removeWidget(row)
            row.deleteLater()
        self._rows = []
        self.status.setText("\n".join(inventory.errors) if inventory.errors else self.tr("%1 installed applications").replace("%1", str(len(inventory.applications))))
        for app in inventory.applications:
            row = _InstalledApplicationRow(app.name, f"{app.source} · {app.installation} · {app.version} · {app.size}\n{app.ref}")
            if app.source == "flatpak":
                permissions = QPushButton(self.tr("Show permissions"))
                permissions.clicked.connect(lambda _checked=False, item=app: self.show_permissions(item))
                row.add_widget(permissions)
                remove = QPushButton(self.tr("Review removal"))
                remove.clicked.connect(lambda _checked=False, item=app: self.actionReviewRequested.emit("remove-installed-flatpak", {"ref": item.ref, "installation": item.installation}))
            else:
                remove = QPushButton(self.tr("Open software manager"))
                remove.clicked.connect(self.open_software_manager)
            row.add_widget(remove)
            self.add_widget(row)
            self._rows.append(row)
        self.inventoryUpdated.emit(inventory)

    def show_permissions(self, app: InstalledApplication):
        if self.service is None or app.source != "flatpak":
            return
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
