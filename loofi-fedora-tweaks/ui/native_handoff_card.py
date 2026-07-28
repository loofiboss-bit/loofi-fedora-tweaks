"""Accessible presentation for explicitly requested native desktop handoffs."""

from __future__ import annotations

from PyQt6.QtCore import QProcess
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from core.catalog_models import NativeHandoffId
from services.desktop.native_handoff import NativeHandoffService
from ui.components.actions import SecondaryButton


class NativeHandoffCard(QFrame):
    """Data-light bridge from an opaque handoff ID to a native Plasma UI."""

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
            description=self.tr("Open this setting in the native Plasma interface"),
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
        availability = self._service.availability(self._handoff_id)
        self.open_button.setEnabled(availability.available)
        self.status_label.setText(availability.detail)
        self.status_label.setAccessibleName(availability.detail)
        self.setProperty(
            "capabilityState",
            availability.state.value,
        )

    def _launch(self) -> None:
        launch = self._service.prepare_launch(self._handoff_id)
        if launch is None:
            self.refresh_availability()
            return
        result = QProcess.startDetached(launch.program, list(launch.arguments))
        started = result[0] if isinstance(result, tuple) else bool(result)
        if not started:
            self.open_button.setEnabled(False)
            message = self.tr("The native Plasma interface could not be started.")
            self.status_label.setText(message)
            self.status_label.setAccessibleName(message)
