"""Installed app presentation; operations are handed to the shared controller."""
from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QLabel, QPushButton, QLayout

from core.catalog_models import NativeHandoffId
from services.software.installed_applications import InstalledApplication, InstalledInventory
from ui.components import Card
from ui.operation_worker import OperationControllerQtAdapter
from ui.native_handoff_card import NativeHandoffCard


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
        self._adapter = OperationControllerQtAdapter(parent=self)
        self._adapter.finished.connect(self.apply_inventory)
        self._adapter.failed.connect(self._failed)
        self._adapter.stopped.connect(lambda: self.refresh_button.setEnabled(self.service is not None))
        self._permissions_adapter = OperationControllerQtAdapter(parent=self)
        self._adapter.stopped.connect(self._notify_stopped)
        self._permissions_adapter.stopped.connect(self._notify_stopped)
        self._permissions_adapter.finished.connect(self._permissions_result)
        self._permissions_adapter.failed.connect(lambda _message: self.status.setText(self.tr("Permissions could not be read.")))
        self.refresh_button.setEnabled(service is not None)

    @property
    def busy(self):
        return self._adapter.busy or self._permissions_adapter.busy

    def request_stop(self):
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
        if self.service is not None and not self._permissions_adapter.busy:
            self.status.setText(self.tr("Reading permissions…"))
            self._permissions_adapter.start(lambda: self.service.permissions(app))

    def _permissions_result(self, permissions):
        values = getattr(permissions, "permissions", ())
        self.status.setText("\n".join(f"{item.category}: {item.value}" for item in values) or self.tr("No permissions were reported. Check Flatpak details if access is unexpected."))
