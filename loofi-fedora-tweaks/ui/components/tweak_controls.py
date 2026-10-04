"""Accessible choice controls with one value API for state-backed tweaks."""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QPoint, QRect, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QPalette
from PyQt6.QtWidgets import QBoxLayout, QButtonGroup, QCheckBox, QComboBox, QPushButton, QSizePolicy, QStyle, QStyleOptionFocusRect, QWidget


class TweakSwitch(QCheckBox):
    """Palette-backed switch retaining native checked and keyboard semantics."""

    def sizeHint(self) -> QSize:
        height = max(20, self.fontMetrics().height())
        return QSize(height * 2 + 16 + self.fontMetrics().horizontalAdvance(self.text()), height + 12)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def hitButton(self, pos: QPoint) -> bool:
        return self.rect().contains(pos)

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        height = max(20, self.fontMetrics().height())
        width = height * 2
        top = (self.height() - height) // 2
        palette = self.palette()
        group = QPalette.ColorGroup.Active if self.isEnabled() else QPalette.ColorGroup.Disabled
        track_role = QPalette.ColorRole.Highlight if self.isChecked() else QPalette.ColorRole.Mid
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(palette.color(group, track_role))
        painter.drawRoundedRect(2, top, width, height, height / 2, height / 2)
        knob = height - 6
        left = 2 + (width - height if self.isChecked() else 0) + 3
        painter.setBrush(palette.color(group, QPalette.ColorRole.HighlightedText if self.isChecked() else QPalette.ColorRole.Base))
        painter.drawEllipse(left, top + 3, knob, knob)
        painter.setPen(palette.color(group, QPalette.ColorRole.Text))
        painter.drawText(QRect(width + 14, 0, max(0, self.width() - width - 14), self.height()), Qt.AlignmentFlag.AlignVCenter, self.text())
        if self.hasFocus():
            focus = QStyleOptionFocusRect()
            focus.initFrom(self)
            focus.rect = self.rect().adjusted(0, 0, -1, -1)
            style = self.style()
            if style is not None:
                style.drawPrimitive(QStyle.PrimitiveElement.PE_FrameFocusRect, focus, painter, self)
        painter.end()


class TweakControl(QWidget):
    """Present booleans, short choices, or arbitrary values without write signals."""

    activated = pyqtSignal(int)

    def __init__(self, kind: str = "auto", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.kind = kind
        self._items: list[tuple[str, Any]] = []
        self._index = -1
        self._editor: QWidget | None = None
        self._buttons: list[QPushButton] = []
        self._button_group: QButtonGroup | None = None
        self._layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)
        self.setObjectName("tweakControl")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

    def minimumSizeHint(self) -> QSize:
        # Allow named choices to reflow at the row's assigned width, while
        # Preferred sizing still reserves their actual useful width.
        return QSize(0, super().minimumSizeHint().height())

    def clear(self) -> None:
        self._items.clear()
        self._index = -1

    def addItem(self, label: str, data: Any) -> None:
        self._items.append((label, data))

    def count(self) -> int:
        return len(self._items)

    def itemData(self, index: int) -> Any:
        return self._items[index][1] if 0 <= index < len(self._items) else None

    def itemText(self, index: int) -> str:
        return self._items[index][0] if 0 <= index < len(self._items) else ""

    def findData(self, data: Any) -> int:
        return next((index for index, (_label, value) in enumerate(self._items) if value == data), -1)

    def currentData(self) -> Any:
        return self.itemData(self._index)

    def currentIndex(self) -> int:
        return self._index

    def currentText(self) -> str:
        return self.itemText(self._index)

    def setCurrentIndex(self, index: int) -> None:
        self._index = index
        self._sync_editor()

    def rebuild(self) -> None:
        """Choose the editor after a complete independent state read."""
        while self._layout.count():
            item = self._layout.takeAt(0)
            assert item is not None
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        if self._button_group is not None:
            self._button_group.deleteLater()
        self._buttons = []
        kind = self.kind
        if kind == "auto":
            boolean = {value for _label, value in self._items} == {"true", "false"}
            semantic = all(label.startswith(("On", "Off", "Show", "Hide")) for label, _value in self._items)
            kind = "switch" if boolean and semantic else "segmented" if 1 < len(self._items) <= 3 else "dropdown"
        # Preserve independently read custom values instead of coercing them.
        if kind == "switch" and {value for _label, value in self._items} != {"true", "false"}:
            kind = "dropdown"
        if kind == "segmented" and len(self._items) > 3:
            kind = "dropdown"
        self.setProperty("controlKind", kind)
        if kind == "switch":
            editor = TweakSwitch(self)
            editor.setObjectName("tweakSwitch")
            editor.clicked.connect(lambda _checked: self._activate(self.findData("true" if editor.isChecked() else "false")))
            self._editor = editor
            self._layout.addWidget(editor)
        elif kind == "segmented":
            self._editor = None
            self._button_group = QButtonGroup(self)
            self._button_group.setExclusive(True)
            for index, (label, _value) in enumerate(self._items):
                button = QPushButton(label, self)
                button.setObjectName("tweakSegment")
                button.setCheckable(True)
                button.setAccessibleName(self.tr("%1: %2").replace("%1", self.accessibleName()).replace("%2", label))
                button.clicked.connect(lambda _checked, selected=index: self._activate(selected))
                self._button_group.addButton(button, index)
                self._buttons.append(button)
                self._layout.addWidget(button)
            if self._buttons:
                self.setFocusProxy(self._buttons[0])
        else:
            combo = QComboBox(self)
            combo.setObjectName("tweakDropdown")
            combo.setMinimumContentsLength(8)
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            for label, value in self._items:
                combo.addItem(label, value)
            combo.activated.connect(self._activate)
            self._editor = combo
            self._layout.addWidget(combo)
        if self._editor is not None:
            self._editor.setAccessibleName(self.accessibleName())
            self.setFocusProxy(self._editor)
        self._sync_editor()

    def _sync_editor(self) -> None:
        if isinstance(self._editor, QCheckBox):
            self._editor.setChecked(self.currentData() == "true")
            self._editor.setText(self.currentText())
        elif isinstance(self._editor, QComboBox):
            self._editor.setCurrentIndex(self._index)
        for index, button in enumerate(self._buttons):
            button.setChecked(index == self._index)

    def _activate(self, index: int) -> None:
        self._index = index
        self._sync_editor()
        self.activated.emit(index)

    def resizeEvent(self, event: Any) -> None:
        super().resizeEvent(event)
        required = sum(button.minimumSizeHint().width() for button in self._buttons) + max(0, len(self._buttons) - 1) * self._layout.spacing()
        self._layout.setDirection(QBoxLayout.Direction.TopToBottom if self._buttons and required > self.width() else QBoxLayout.Direction.LeftToRight)
