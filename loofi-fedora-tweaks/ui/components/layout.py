"""Responsive page scaffolding and compatibility layout primitives."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QFontMetrics
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.components.actions import ActionBar
from ui.design import DesignTokens


@dataclass(frozen=True)
class LayoutMetrics:
    """Font-derived dimensions used by the desktop shell."""

    line_height: int
    spacing_small: int
    spacing_medium: int
    spacing_large: int
    page_margin: int
    sidebar_width: int
    sidebar_collapsed_width: int
    header_height: int
    status_height: int

    @classmethod
    def from_widget(cls, widget: QWidget) -> "LayoutMetrics":
        try:
            fm = QFontMetrics(widget.font())
            line_height = max(14, fm.height())
        except (AttributeError, TypeError):
            line_height = 16
        return cls(
            line_height=line_height,
            spacing_small=max(6, int(line_height * 0.45)),
            spacing_medium=max(10, int(line_height * 0.75)),
            spacing_large=max(18, int(line_height * 1.3)),
            page_margin=max(24, int(line_height * 1.8)),
            sidebar_width=min(272, max(248, int(line_height * 17))),
            sidebar_collapsed_width=min(72, max(64, int(line_height * 4))),
            header_height=max(68, int(line_height * 4.8)),
            status_height=max(28, int(line_height * 2.1)),
        )


class PageHeader(QFrame):
    """Page title, location, description, and compact caller-owned actions."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("pageHeader")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(4)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(12)
        top_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.eyebrow = QPushButton("")
        self.eyebrow.setObjectName("pageHeaderEyebrow")
        self.eyebrow.setFlat(True)
        self.eyebrow.setCursor(Qt.CursorShape.PointingHandCursor)
        self.eyebrow.setMinimumSize(36, 36)
        self.eyebrow.setVisible(False)
        top_row.addWidget(self.eyebrow)
        top_row.addStretch()
        self.action_bar = ActionBar(self)
        self.action_bar.setAccessibleName(self.tr("Page actions"))
        self.actions_layout = self.action_bar.row_layout
        top_row.addWidget(self.action_bar)

        self.title = QLabel("")
        self.title.setObjectName("pageHeaderTitle")
        self.title.setWordWrap(True)
        self.description = QLabel("")
        self.description.setObjectName("pageHeaderDescription")
        self.description.setWordWrap(True)

        layout.addLayout(top_row)
        layout.addWidget(self.title)
        layout.addWidget(self.description)
        self.setAccessibleName(self.tr("Page header"))

    def set_content(self, area: str, title: str, description: str = "") -> None:
        self.eyebrow.setText(area)
        self.eyebrow.setAccessibleName(area)
        normalized_area = " ".join(str(area).split()).casefold()
        normalized_title = " ".join(str(title).split()).casefold()
        self.eyebrow.setVisible(
            bool(normalized_area) and normalized_area != normalized_title
        )
        self.title.setText(title)
        self.description.setText(description)
        self.description.setVisible(bool(description))
        self.setAccessibleName(title or self.tr("Page header"))
        self.setAccessibleDescription(description)

    def add_action(self, widget: QWidget, *, primary: bool = False) -> None:
        self.action_bar.add_action(widget, primary=primary)

    def clear_actions(self) -> None:
        """Detach route-owned actions before the shell changes page."""
        self.action_bar.clear_actions()


class ContentColumn(QWidget):
    """Centered bounded content area that never owns domain behavior."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        tokens = DesignTokens()
        self.setObjectName("contentColumn")
        self.setMaximumWidth(tokens.content_max_width)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(tokens.space_6, tokens.space_6, tokens.space_6, tokens.space_8)
        self.body.setSpacing(tokens.space_4)
        self.setAccessibleName(self.tr("Page content"))

    def add_widget(self, widget: QWidget, stretch: int = 0) -> None:
        self.body.addWidget(widget, stretch)

    def add_layout(self, layout, stretch: int = 0) -> None:
        self.body.addLayout(layout, stretch)


class PageScaffold(QWidget):
    """Stable content hierarchy below the shell-owned page header."""

    def __init__(
        self,
        accessible_name: str = "",
        description: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("pageScaffold")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.addStretch()
        self.content = ContentColumn(self)
        self.content_column = self.content
        self.content_layout = self.content.body
        content_row.addWidget(self.content, 1)
        content_row.addStretch()
        outer.addLayout(content_row, 1)
        self.setAccessibleName(accessible_name or self.tr("Page content"))
        self.setAccessibleDescription(description)

    def set_page_description(self, accessible_name: str, description: str = "") -> None:
        self.setAccessibleName(accessible_name or self.tr("Page content"))
        self.setAccessibleDescription(description)

    def add_widget(self, widget: QWidget, stretch: int = 0) -> None:
        self.content.add_widget(widget, stretch)

    def add_layout(self, layout, stretch: int = 0) -> None:
        self.content.add_layout(layout, stretch)


class AdaptiveGrid(QWidget):
    """Responsive one-to-three-column grid for shared cards."""

    def __init__(
        self,
        min_column_width: int = 260,
        parent: QWidget | None = None,
        *,
        column_breakpoints: tuple[tuple[int, int], ...] = (),
    ) -> None:
        super().__init__(parent)
        self.min_column_width = min_column_width
        self.column_breakpoints = tuple(sorted(column_breakpoints))
        self._items: list[QWidget] = []
        self._columns = 0
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(16)
        self.grid.setVerticalSpacing(16)

    def add_card(self, widget: QWidget) -> None:
        self._items.append(widget)
        self._reflow(max(1, self.width()))

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):  # noqa: N802 - Qt layout compatibility
        return self.grid.itemAt(index)

    def resizeEvent(self, event) -> None:
        self._reflow(max(1, self.width()))
        super().resizeEvent(event)

    def _reflow(self, width: int) -> None:
        if self.column_breakpoints:
            columns = 1
            for minimum_width, count in self.column_breakpoints:
                if width >= minimum_width:
                    columns = max(1, count)
        else:
            columns = max(1, min(3, width // self.min_column_width))
        if columns == self._columns and self.grid.count() == len(self._items):
            return
        self._columns = columns
        while self.grid.count():
            self.grid.takeAt(0)
        for index, widget in enumerate(self._items):
            row, col = divmod(index, columns)
            self.grid.addWidget(widget, row, col)
        for col in range(columns):
            self.grid.setColumnStretch(col, 1)


def make_page_title(text: str) -> QLabel:
    """Return a compatibility title label for pages not yet scaffolded."""
    label = QLabel(text)
    label.setObjectName("header")
    font = QFont(label.font())
    font.setBold(True)
    label.setFont(font)
    label.setWordWrap(True)
    label.setAccessibleName(text)
    return label
