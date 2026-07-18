"""Reusable content surfaces and property rows."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent, QMouseEvent
from PyQt6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.components.actions import GhostButton


class Card(QFrame):
    """Non-interactive surface for one coherent group of content."""

    def __init__(
        self,
        title: str = "",
        description: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("componentCard")
        self.setProperty("componentCard", True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(16, 16, 16, 16)
        self.body.setSpacing(12)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("cardTitle")
        self.title_label.setWordWrap(True)
        self.title_label.setVisible(bool(title))
        self.description_label = QLabel(description)
        self.description_label.setObjectName("cardDescription")
        self.description_label.setWordWrap(True)
        self.description_label.setVisible(bool(description))
        self.body.addWidget(self.title_label)
        self.body.addWidget(self.description_label)
        if title:
            self.setAccessibleName(title)
        if description:
            self.setAccessibleDescription(description)

    def set_heading(self, title: str, description: str = "") -> None:
        self.title_label.setText(title)
        self.title_label.setVisible(bool(title))
        self.description_label.setText(description)
        self.description_label.setVisible(bool(description))
        self.setAccessibleName(title)
        self.setAccessibleDescription(description)

    def add_widget(self, widget: QWidget, stretch: int = 0) -> None:
        self.body.addWidget(widget, stretch)


class ClickableCard(Card):
    """Whole-card action with mouse, Enter, and Space activation."""

    activated = pyqtSignal(str)

    def __init__(
        self,
        title: str,
        description: str,
        activation_id: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(title, description, parent)
        self.activation_id = activation_id
        self.route_id = activation_id
        self.setObjectName("clickableCard")
        self.setProperty("clickableCard", True)
        self.setProperty("activationId", activation_id)
        self.setProperty("interactionState", "default")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._pressed = False

    def add_widget(self, widget: QWidget, stretch: int = 0) -> None:
        if isinstance(widget, QAbstractButton) or widget.focusPolicy() != Qt.FocusPolicy.NoFocus:
            raise ValueError("ClickableCard content cannot contain nested interactive controls")
        super().add_widget(widget, stretch)

    def activate(self) -> None:
        if self.isEnabled():
            self.activated.emit(self.activation_id)

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        if event is None:
            return
        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space}:
            if not event.isAutoRepeat() and self.isEnabled():
                self._pressed = True
                self._set_interaction_state("active")
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent | None) -> None:
        if event is None:
            return
        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space}:
            should_activate = self._pressed and self.isEnabled()
            self._pressed = False
            self._set_interaction_state("default")
            if should_activate:
                self.activate()
            event.accept()
            return
        super().keyReleaseEvent(event)

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event is None:
            return
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.isEnabled()
            and self.rect().contains(event.position().toPoint())
        ):
            self._pressed = True
            self._set_interaction_state("active")
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        if event is None:
            return
        should_activate = (
            event.button() == Qt.MouseButton.LeftButton
            and self._pressed
            and self.rect().contains(event.position().toPoint())
        )
        self._pressed = False
        self._set_interaction_state("default")
        if should_activate:
            self.activate()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _set_interaction_state(self, state: str) -> None:
        self.setProperty("interactionState", state)
        self.style().unpolish(self)
        self.style().polish(self)


class DefinitionRow(QWidget):
    """One nearby label/value pair with an optional caller-owned copy action."""

    copyRequested = pyqtSignal(str)

    def __init__(
        self,
        label: str,
        value: str,
        *,
        copyable: bool = False,
        description: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("definitionRow")
        self._value = value
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 8, 0, 8)
        row.setSpacing(12)
        row.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.label = QLabel(label)
        self.label.setObjectName("definitionLabel")
        self.label.setWordWrap(True)
        self.value = QLabel(value)
        self.value.setObjectName("definitionValue")
        self.value.setWordWrap(True)
        self.value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByKeyboard | Qt.TextInteractionFlag.TextSelectableByMouse)
        self.copy_button = GhostButton(
            self.tr("Copy"),
            description=self.tr("Copy %1").replace("%1", label),
        )
        self.copy_button.setVisible(copyable)
        self.copy_button.clicked.connect(lambda: self.copyRequested.emit(self._value))

        row.addWidget(self.label, 2)
        row.addWidget(self.value, 3)
        row.addWidget(self.copy_button)
        self.setAccessibleName(label)
        self.setAccessibleDescription(description or value)

    def set_value(self, value: str) -> None:
        self._value = value
        self.value.setText(value)
        self.setAccessibleDescription(value)


class DefinitionList(Card):
    """Stack of consistent property rows."""

    def __init__(
        self,
        title: str = "",
        description: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(title, description, parent)
        self.setObjectName("definitionList")
        self.rows: list[DefinitionRow] = []

    def add_row(
        self,
        label: str,
        value: str,
        *,
        copyable: bool = False,
        description: str = "",
    ) -> DefinitionRow:
        row = DefinitionRow(
            label,
            value,
            copyable=copyable,
            description=description,
            parent=self,
        )
        self.rows.append(row)
        self.body.addWidget(row)
        return row
