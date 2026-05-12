"""Shared responsive layout primitives for the PyQt desktop UI."""

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
        fm = QFontMetrics(widget.font())
        line_height = max(14, fm.height())
        return cls(
            line_height=line_height,
            spacing_small=max(6, int(line_height * 0.45)),
            spacing_medium=max(10, int(line_height * 0.75)),
            spacing_large=max(18, int(line_height * 1.3)),
            page_margin=max(24, int(line_height * 1.8)),
            sidebar_width=max(248, int(line_height * 17)),
            sidebar_collapsed_width=max(58, int(line_height * 4)),
            header_height=max(68, int(line_height * 4.8)),
            status_height=max(28, int(line_height * 2.1)),
        )


class PageHeader(QFrame):
    """Page title, location, and short description used by the main shell."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("pageHeader")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 12, 22, 10)
        layout.setSpacing(2)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(10)

        self.eyebrow = QPushButton("")
        self.eyebrow.setObjectName("pageHeaderEyebrow")
        self.eyebrow.setFlat(True)
        self.eyebrow.setCursor(Qt.CursorShape.PointingHandCursor)
        top_row.addWidget(self.eyebrow)
        top_row.addStretch()
        self.actions_layout = QHBoxLayout()
        self.actions_layout.setContentsMargins(0, 0, 0, 0)
        self.actions_layout.setSpacing(8)
        top_row.addLayout(self.actions_layout)

        self.title = QLabel("")
        self.title.setObjectName("pageHeaderTitle")
        self.description = QLabel("")
        self.description.setObjectName("pageHeaderDescription")
        self.description.setWordWrap(True)

        layout.addLayout(top_row)
        layout.addWidget(self.title)
        layout.addWidget(self.description)

    def set_content(self, area: str, title: str, description: str = "") -> None:
        self.eyebrow.setText(area)
        self.title.setText(title)
        self.description.setText(description)
        self.description.setVisible(bool(description))


class Section(QFrame):
    """Lightweight section container for related controls."""

    def __init__(self, title: str = "", description: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("contentSection")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(18, 16, 18, 16)
        self.body.setSpacing(12)

        if title:
            title_label = QLabel(title)
            title_label.setObjectName("sectionTitle")
            self.body.addWidget(title_label)
        if description:
            desc_label = QLabel(description)
            desc_label.setObjectName("descriptionText")
            desc_label.setWordWrap(True)
            self.body.addWidget(desc_label)


class ActionRow(QWidget):
    """Horizontal action strip with consistent spacing."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.row_layout = QHBoxLayout(self)
        self.row_layout.setContentsMargins(0, 0, 0, 0)
        self.row_layout.setSpacing(10)
        self.row_layout.addStretch()

    def add_action(self, widget: QWidget) -> None:
        index = max(0, self.row_layout.count() - 1)
        self.row_layout.insertWidget(index, widget)


class RouteCard(QFrame):
    """Clickable-looking route card used by home and overview pages."""

    def __init__(
        self,
        title: str,
        description: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("routeCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("routeCardTitle")
        title_label.setWordWrap(True)
        desc_label = QLabel(description)
        desc_label.setObjectName("routeCardDescription")
        desc_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(desc_label)
        layout.addStretch()


class AdaptiveGrid(QWidget):
    """Simple responsive grid that can be reflowed from resize handlers."""

    def __init__(self, min_column_width: int = 260, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.min_column_width = min_column_width
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
        """Return the number of managed cards for layout-test compatibility."""
        return len(self._items)

    def itemAt(self, index: int):
        """Expose the underlying grid item for callers that treat this as a layout."""
        return self.grid.itemAt(index)

    def resizeEvent(self, event) -> None:
        self._reflow(max(1, self.width()))
        super().resizeEvent(event)

    def _reflow(self, width: int) -> None:
        columns = max(1, min(3, width // self.min_column_width))
        if columns == self._columns and self.grid.count() == len(self._items):
            return
        self._columns = columns
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget() if item else None
            if widget is not None:
                widget.setParent(None)
        for index, widget in enumerate(self._items):
            row, col = divmod(index, columns)
            self.grid.addWidget(widget, row, col)
        for col in range(columns):
            self.grid.setColumnStretch(col, 1)


def make_page_title(text: str) -> QLabel:
    """Return a consistent page title label."""
    label = QLabel(text)
    label.setObjectName("header")
    font = QFont(label.font())
    font.setBold(True)
    label.setFont(font)
    label.setWordWrap(True)
    return label
