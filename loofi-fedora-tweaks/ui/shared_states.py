"""Reusable presentation-only states for standard desktop workflows."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class _MessageState(QFrame):
    """Common accessible title and message presentation."""

    def __init__(self, title: str, message: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(16, 14, 16, 14)
        self.body.setSpacing(6)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("stateTitle")
        self.message_label = QLabel(message)
        self.message_label.setObjectName("stateMessage")
        self.message_label.setWordWrap(True)
        self.body.addWidget(self.title_label)
        self.body.addWidget(self.message_label)
        self.setAccessibleName(title)
        self.setAccessibleDescription(message)

    def set_message(self, message: str) -> None:
        self.message_label.setText(message)
        self.setAccessibleDescription(message)


class LoadingState(_MessageState):
    """Busy presentation that does not start or own background work."""

    def __init__(self, message: str = "", parent: QWidget | None = None) -> None:
        super().__init__(self.tr("Loading"), message, parent)
        self.setObjectName("loadingState")
        self.setProperty("presentationState", "loading")
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setAccessibleName(self.tr("Loading progress"))
        self.body.addWidget(self.progress)


class EmptyState(_MessageState):
    """Empty-result presentation with an optional caller-owned action."""

    actionRequested = pyqtSignal()

    def __init__(
        self,
        title: str,
        message: str = "",
        *,
        action_text: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(title, message, parent)
        self.setObjectName("emptyState")
        self.setProperty("presentationState", "empty")
        self.action_button = QPushButton(action_text)
        self.action_button.setAccessibleName(action_text)
        self.action_button.setVisible(bool(action_text))
        self.action_button.clicked.connect(self.actionRequested)
        self.body.addWidget(self.action_button)


class UnavailableState(_MessageState):
    """Unavailable-capability presentation with plain-language guidance."""

    def __init__(self, title: str, message: str = "", parent: QWidget | None = None) -> None:
        super().__init__(title, message, parent)
        self.setObjectName("unavailableState")
        self.setProperty("presentationState", "unavailable")


class ResultBanner(_MessageState):
    """Result presentation distinguished by text and a semantic property."""

    _KINDS = frozenset({"info", "success", "warning", "error"})

    def __init__(
        self,
        title: str = "",
        message: str = "",
        *,
        kind: str = "info",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(title, message, parent)
        self.setObjectName("resultBanner")
        self.set_result(kind, title, message)

    def set_result(self, kind: str, title: str, message: str) -> None:
        normalized = kind if kind in self._KINDS else "info"
        self.setProperty("resultKind", normalized)
        self.title_label.setText(title)
        self.message_label.setText(message)
        self.setAccessibleName(title)
        self.setAccessibleDescription(message)


class ActionProgress(QFrame):
    """Progress and status presentation; execution remains caller-owned."""

    def __init__(self, message: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("actionProgress")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.status_label = QLabel(message)
        self.status_label.setWordWrap(True)
        self.status_label.setAccessibleName(self.tr("Action status"))
        self.progress_bar = QProgressBar()
        self.progress_bar.setAccessibleName(self.tr("Action progress"))
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        self.set_busy(message)

    def set_busy(self, message: str) -> None:
        self.setProperty("progressState", "busy")
        self.status_label.setText(message)
        self.progress_bar.setRange(0, 0)

    def set_progress(self, value: int, message: str = "") -> None:
        bounded = max(0, min(100, int(value)))
        self.setProperty("progressState", "determinate")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(bounded)
        if message:
            self.status_label.setText(message)


class DetailsDisclosure(QWidget):
    """Keyboard-accessible disclosure for technical output."""

    def __init__(
        self,
        details: str = "",
        *,
        summary: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("detailsDisclosure")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.toggle_button = QToolButton()
        self.toggle_button.setCheckable(True)
        self.toggle_button.setText(summary or self.tr("Show details"))
        self.toggle_button.setAccessibleName(summary or self.tr("Show details"))
        self.details = QPlainTextEdit(details)
        self.details.setReadOnly(True)
        self.details.setAccessibleName(self.tr("Technical details"))
        self.details.setVisible(False)
        self.toggle_button.toggled.connect(self._set_expanded)
        layout.addWidget(self.toggle_button)
        layout.addWidget(self.details)

    def set_details(self, details: str) -> None:
        self.details.setPlainText(details)

    def _set_expanded(self, expanded: bool) -> None:
        self.setProperty("expanded", expanded)
        self.details.setVisible(expanded)
        self.toggle_button.setText(
            self.tr("Hide details") if expanded else self.tr("Show details")
        )
