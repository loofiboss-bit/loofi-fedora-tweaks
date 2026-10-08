"""Accessible presentation for explicitly requested native desktop handoffs."""

from __future__ import annotations

from PyQt6.QtCore import QProcess, pyqtSignal
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from core.catalog_models import NativeHandoffId
from core.platform.profile import PlatformProfile
from services.desktop.native_handoff import NativeHandoffService
from services.system.system import SystemManager
from ui.components.actions import SecondaryButton


class NativeHandoffCard(QFrame):
    """Data-light bridge from an opaque handoff ID to a native desktop UI."""

    def __init__(
        self,
        handoff_id: NativeHandoffId,
        *,
        title: str,
        description: str,
        button_text: str,
        service: NativeHandoffService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("nativeHandoffCard")
        self._handoff_id = handoff_id
        self._service = service or NativeHandoffService()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("nativeHandoffTitle")
        self.description_label = QLabel(description)
        self.description_label.setObjectName("nativeHandoffDescription")
        self.description_label.setWordWrap(True)
        self.status_label = QLabel(self.tr("Availability is checked when this view opens."))
        self.status_label.setObjectName("nativeHandoffStatus")
        self.status_label.setWordWrap(True)

        self.open_button = SecondaryButton(
            button_text,
            description=self.tr("Open this setting in the native desktop interface"),
        )
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self._launch)

        layout.addWidget(self.title_label)
        layout.addWidget(self.description_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.open_button)

        self.setAccessibleName(title)
        self.setAccessibleDescription(description)

    @property
    def handoff_id(self) -> NativeHandoffId:
        return self._handoff_id

    def refresh_availability(self) -> None:
        """Refresh presentation only after the owning route is activated."""
        # Real native handoffs are always evaluated against the immutable
        # platform profile.  Test doubles and explicitly supplied services
        # keep the small one-argument contract used by embedders.
        if type(self._service) is NativeHandoffService:
            profile: PlatformProfile = SystemManager.get_platform_profile()
            availability = self._service.availability(
                self._handoff_id,
                profile=profile,
            )
        else:
            availability = self._service.availability(self._handoff_id)
        self.open_button.setEnabled(availability.available)
        self.status_label.setText(availability.detail)
        self.status_label.setAccessibleName(availability.detail)
        self.setProperty(
            "capabilityState",
            availability.state.value,
        )

    def _launch(self) -> None:
        if type(self._service) is NativeHandoffService:
            profile: PlatformProfile = SystemManager.get_platform_profile()
            launch = self._service.prepare_launch(
                self._handoff_id,
                profile=profile,
            )
        else:
            launch = self._service.prepare_launch(self._handoff_id)
        if launch is None:
            self.refresh_availability()
            return
        result = QProcess.startDetached(launch.program, list(launch.arguments))
        started = result[0] if isinstance(result, tuple) else bool(result)
        if not started:
            self.open_button.setEnabled(False)
            message = self.tr("The native interface could not be started.")
            self.status_label.setText(message)
            self.status_label.setAccessibleName(message)


class ManagedNativeHandoffCard(NativeHandoffCard):
    """Route-owned discovery and launch preparation outside the GUI thread."""

    stopped = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from ui.operation_worker import OperationControllerQtAdapter

        self._adapter = OperationControllerQtAdapter(parent=self)
        self._adapter.finished.connect(self._completed)
        self._adapter.failed.connect(self._failed)
        self._adapter.stopped.connect(self.stopped.emit)
        self._closing = False
        self._launch_requested = False
        self.status_label.setText(self.tr("Availability is checked before opening."))
        self.open_button.setEnabled(True)
        self.check_button = SecondaryButton(self.tr("Check availability"))
        self.check_button.clicked.connect(self.refresh_availability)
        self.layout().addWidget(self.check_button)
        self._adapter.stopped.connect(lambda: self.check_button.setEnabled(not self._closing))

    @property
    def busy(self) -> bool:
        return bool(self._adapter.busy)

    def request_stop(self) -> None:
        self._closing = True
        self.open_button.setEnabled(False)
        self.check_button.setEnabled(False)
        self._adapter.cancel()

    def cleanup(self, timeout_ms: int = 1000) -> bool:
        self.request_stop()
        return bool(self._adapter.close(timeout_ms))

    def _start(self, *, launch: bool) -> None:
        if self._closing or self.busy:
            return
        self._launch_requested = launch
        self.open_button.setEnabled(False)
        self.check_button.setEnabled(False)
        self.status_label.setText(self.tr("Checking native settings…"))

        def read():
            profile = SystemManager.get_platform_profile()
            if launch:
                prepared = self._service.prepare_launch(self._handoff_id, profile=profile)
                return prepared, self._service.availability(self._handoff_id, profile=profile) if prepared is None else None
            return self._service.availability(self._handoff_id, profile=profile)

        self._adapter.start(read)

    def refresh_availability(self) -> None:
        self._start(launch=False)

    def _launch(self) -> None:
        self._start(launch=True)

    def _completed(self, result) -> None:
        if self._closing:
            return
        if self._launch_requested:
            prepared, availability = result
            if prepared is None:
                self.open_button.setEnabled(False)
                self.status_label.setText(availability.detail)
                self.status_label.setAccessibleName(availability.detail)
                self.setProperty("capabilityState", availability.state.value)
                return
            launched = QProcess.startDetached(prepared.program, list(prepared.arguments))
            started = launched[0] if isinstance(launched, tuple) else bool(launched)
            self.open_button.setEnabled(started)
            self.status_label.setText(self.tr("Native settings opened. Return here to refresh after making changes.") if started else self.tr("The native interface could not be started."))
        else:
            self.open_button.setEnabled(result.available)
            self.status_label.setText(result.detail)
            self.setProperty("capabilityState", result.state.value)
        self.status_label.setAccessibleName(self.status_label.text())

    def _failed(self, _message) -> None:
        if not self._closing:
            self.open_button.setEnabled(False)
            self.status_label.setText(self.tr("Native settings could not be checked. Reopen this view to retry."))
            self.status_label.setAccessibleName(self.status_label.text())
            self.setProperty("capabilityState", "unavailable")
