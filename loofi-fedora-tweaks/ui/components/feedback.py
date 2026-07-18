"""Shared textual status, progress, and disclosure components."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ui.components.actions import SecondaryButton


_STATUS_KINDS = frozenset({"info", "success", "warning", "error", "neutral"})


def _normalized_kind(kind: str) -> str:
    return kind if kind in _STATUS_KINDS else "info"


def _status_icon(widget: QWidget, kind: str):
    icon_by_kind = {
        "info": QStyle.StandardPixmap.SP_MessageBoxInformation,
        "success": QStyle.StandardPixmap.SP_DialogApplyButton,
        "warning": QStyle.StandardPixmap.SP_MessageBoxWarning,
        "error": QStyle.StandardPixmap.SP_MessageBoxCritical,
        "neutral": QStyle.StandardPixmap.SP_FileDialogInfoView,
    }
    style = widget.style()
    if style is None:
        return QIcon()
    return style.standardIcon(icon_by_kind[_normalized_kind(kind)])


def _repolish(widget: QWidget) -> None:
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)


class StatusBadge(QFrame):
    """Compact status expressed through icon, text, and semantic color."""

    def __init__(
        self,
        text: str,
        *,
        kind: str = "info",
        description: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("statusBadge")
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 4, 8, 4)
        row.setSpacing(8)
        row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.icon_label = QLabel()
        self.icon_label.setObjectName("statusBadgeIcon")
        self.text_label = QLabel(text)
        self.text_label.setObjectName("statusBadgeText")
        row.addWidget(self.icon_label)
        row.addWidget(self.text_label)
        self.set_status(text, kind=kind, description=description)

    def set_status(self, text: str, *, kind: str = "info", description: str = "") -> None:
        normalized = _normalized_kind(kind)
        self.setProperty("statusKind", normalized)
        self.text_label.setText(text)
        self.icon_label.setPixmap(_status_icon(self, normalized).pixmap(16, 16))
        self.setAccessibleName(text)
        self.setAccessibleDescription(description or normalized)
        _repolish(self)


class InlineNotice(QFrame):
    """Plain-language notice with non-color-only semantic status."""

    def __init__(
        self,
        title: str,
        message: str = "",
        *,
        kind: str = "info",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("inlineNotice")
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 12, 12, 12)
        row.setSpacing(10)
        row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.icon_label = QLabel()
        self.icon_label.setObjectName("inlineNoticeIcon")
        row.addWidget(self.icon_label, 0)
        copy = QVBoxLayout()
        copy.setContentsMargins(0, 0, 0, 0)
        copy.setSpacing(4)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("noticeTitle")
        self.message_label = QLabel(message)
        self.message_label.setObjectName("noticeMessage")
        self.message_label.setWordWrap(True)
        self.message_label.setVisible(bool(message))
        copy.addWidget(self.title_label)
        copy.addWidget(self.message_label)
        row.addLayout(copy, 1)
        self.set_notice(kind, title, message)

    def set_notice(self, kind: str, title: str, message: str = "") -> None:
        normalized = _normalized_kind(kind)
        self.setProperty("noticeKind", normalized)
        self.setProperty("resultKind", normalized)
        self.icon_label.setPixmap(_status_icon(self, normalized).pixmap(20, 20))
        self.title_label.setText(title)
        self.message_label.setText(message)
        self.message_label.setVisible(bool(message))
        self.setAccessibleName(title)
        self.setAccessibleDescription(message or normalized)
        _repolish(self)

    def set_result(self, kind: str, title: str, message: str) -> None:
        """Update a caller-owned operation result."""
        self.set_notice(kind, title, message)


class _MessageState(QFrame):
    """Common accessible title and message presentation."""

    def __init__(self, title: str, message: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(16, 12, 16, 12)
        self.body.setSpacing(8)
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
        self.action_button = SecondaryButton(
            action_text,
            description=message,
        )
        self.action_button.setVisible(bool(action_text))
        self.action_button.clicked.connect(self.actionRequested)
        self.body.addWidget(self.action_button)


class UnavailableState(_MessageState):
    """Unavailable-capability presentation with plain-language guidance."""

    def __init__(self, title: str, message: str = "", parent: QWidget | None = None) -> None:
        super().__init__(title, message, parent)
        self.setObjectName("unavailableState")
        self.setProperty("presentationState", "unavailable")


class ActionProgress(QFrame):
    """Progress and status presentation; execution remains caller-owned."""

    def __init__(self, message: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("actionProgress")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
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
        self.setAccessibleName(self.tr("Action in progress"))
        self.setAccessibleDescription(message)

    def set_progress(self, value: int, message: str = "") -> None:
        bounded = max(0, min(100, int(value)))
        self.setProperty("progressState", "determinate")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(bounded)
        if message:
            self.status_label.setText(message)
        self.setAccessibleName(self.tr("Action progress"))
        self.setAccessibleDescription(
            self.tr("%1 percent. %2").replace("%1", str(bounded)).replace(
                "%2", message
            ).strip()
        )


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
        layout.setSpacing(8)
        self._summary = summary
        self.toggle_button = QToolButton()
        self.toggle_button.setObjectName("disclosureButton")
        self.toggle_button.setProperty("buttonRole", "ghost")
        self.toggle_button.setCheckable(True)
        self.toggle_button.setText(summary or self.tr("Show details"))
        self.toggle_button.setAccessibleName(summary or self.tr("Show details"))
        self.toggle_button.setAccessibleDescription(self.tr("Show technical details"))
        self.details = QPlainTextEdit(details)
        self.details.setReadOnly(True)
        self.details.setAccessibleName(self.tr("Technical details"))
        self.details.setVisible(False)
        self.toggle_button.toggled.connect(self._set_expanded)
        layout.addWidget(self.toggle_button)
        layout.addWidget(self.details)
        self.setAccessibleName(summary or self.tr("Technical details"))

    def set_details(self, details: str) -> None:
        self.details.setPlainText(details)
        self.details.setAccessibleDescription(details)
        self.setAccessibleDescription(details)

    def _set_expanded(self, expanded: bool) -> None:
        self.setProperty("expanded", expanded)
        self.details.setVisible(expanded)
        collapsed_text = self._summary or self.tr("Show details")
        text = self.tr("Hide details") if expanded else collapsed_text
        self.toggle_button.setText(text)
        self.toggle_button.setAccessibleName(text)
        self.toggle_button.setAccessibleDescription(
            self.tr("Hide technical details") if expanded else self.tr("Show technical details")
        )
