"""Presentation-only responsive section navigation."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QEvent, QRect, QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.icon_pack import get_qicon


@dataclass(frozen=True)
class SectionItem:
    """Data-only presentation metadata for one section."""

    section_id: str
    label: str
    description: str = ""
    status: str = ""
    icon: str = ""


class SectionNavigator(QFrame):
    """Full-label rail with an accessible narrow selector fallback."""

    sectionActivated = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sectionNavigator")
        self.setAccessibleName(self.tr("Sections"))
        self._sections: tuple[SectionItem, ...] = ()
        self._suppress_signal = False
        self._compact = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.rail = QListWidget(self)
        self.rail.setObjectName("sectionRail")
        self.rail.setAccessibleName(self.tr("Sections"))
        self.rail.setWordWrap(True)
        self.rail.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.rail.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.rail.currentRowChanged.connect(self._on_rail_changed)
        layout.addWidget(self.rail)

        self.selector = QComboBox(self)
        self.selector.setObjectName("sectionSelector")
        self.selector.setAccessibleName(self.tr("Section"))
        self.selector.currentIndexChanged.connect(self._on_selector_changed)
        self.selector.hide()
        layout.addWidget(self.selector)
        self._apply_mode(False)

    def set_sections(self, sections: tuple[SectionItem, ...] | list[SectionItem]) -> None:
        self._suppress_signal = True
        self._sections = tuple(sections)
        self.rail.clear()
        self.selector.clear()
        for section in self._sections:
            visible_label = (
                self.tr("%1 — %2").replace("%1", section.label).replace("%2", section.status)
                if section.status
                else section.label
            )
            item = QListWidgetItem(visible_label)
            item.setData(Qt.ItemDataRole.UserRole, section.section_id)
            item.setData(Qt.ItemDataRole.AccessibleTextRole, section.label)
            item.setData(
                Qt.ItemDataRole.AccessibleDescriptionRole,
                section.description or section.status,
            )
            item.setToolTip(section.description or section.label)
            if section.icon:
                icon = get_qicon(section.icon, size=20)
                item.setIcon(icon)
            item.setSizeHint(item.sizeHint().expandedTo(self._minimum_row_size(visible_label)))
            self.rail.addItem(item)
            if section.icon:
                self.selector.addItem(icon, section.label, section.section_id)
            else:
                self.selector.addItem(section.label, section.section_id)
            index = self.selector.count() - 1
            self.selector.setItemData(index, section.description or section.label, Qt.ItemDataRole.ToolTipRole)
            self.selector.setItemData(index, section.label, Qt.ItemDataRole.AccessibleTextRole)
            self.selector.setItemData(
                index,
                section.description or section.status,
                Qt.ItemDataRole.AccessibleDescriptionRole,
            )
        if self._sections:
            self.rail.setCurrentRow(0)
            self.selector.setCurrentIndex(0)
        self._suppress_signal = False

    def sections(self) -> tuple[SectionItem, ...]:
        return self._sections

    def section_ids(self) -> tuple[str, ...]:
        return tuple(section.section_id for section in self._sections)

    def set_active_section(self, section_id: str) -> None:
        for index, section in enumerate(self._sections):
            if section.section_id == section_id:
                self._suppress_signal = True
                self.rail.setCurrentRow(index)
                self.selector.setCurrentIndex(index)
                self._suppress_signal = False
                return

    def active_section_id(self) -> str:
        index = self.selector.currentIndex() if self._compact else self.rail.currentRow()
        if 0 <= index < len(self._sections):
            return str(self._sections[index].section_id)
        return ""

    def set_compact(self, compact: bool) -> None:
        """Select rail or compact mode from shell-owned responsive policy."""
        self._compact = compact
        self._apply_mode(compact)

    def refresh_icons(self) -> None:
        """Rebuild semantic icon tints after a live theme change."""
        for index, section in enumerate(self._sections):
            if not section.icon:
                continue
            icon = get_qicon(section.icon, size=20)
            rail_item = self.rail.item(index)
            if rail_item is not None:
                rail_item.setIcon(icon)
            self.selector.setItemIcon(index, icon)

    def is_compact(self) -> bool:
        return self._compact

    def changeEvent(self, event) -> None:
        if event is not None and event.type() == QEvent.Type.FontChange:
            self._refresh_row_sizes()
        super().changeEvent(event)

    def _minimum_row_size(self, text: str) -> QSize:
        bounds = self.rail.fontMetrics().boundingRect(
            QRect(0, 0, 180, 1000),
            Qt.TextFlag.TextWordWrap,
            text,
        )
        return QSize(208, max(44, bounds.height() + 16))

    def _refresh_row_sizes(self) -> None:
        for index in range(self.rail.count()):
            item = self.rail.item(index)
            if item is not None:
                item.setSizeHint(self._minimum_row_size(item.text()))

    def _apply_mode(self, compact: bool) -> None:
        self._compact = compact
        self.setMinimumWidth(0 if compact else 208)
        self.setMaximumWidth(16777215 if compact else 224)
        self.rail.setVisible(not compact)
        self.selector.setVisible(compact)

    def _on_rail_changed(self, index: int) -> None:
        if self._suppress_signal or index < 0 or index >= len(self._sections):
            return
        self._suppress_signal = True
        self.selector.setCurrentIndex(index)
        self._suppress_signal = False
        self.sectionActivated.emit(self._sections[index].section_id)

    def _on_selector_changed(self, index: int) -> None:
        if self._suppress_signal or index < 0 or index >= len(self._sections):
            return
        self._suppress_signal = True
        self.rail.setCurrentRow(index)
        self._suppress_signal = False
        self.sectionActivated.emit(self._sections[index].section_id)


@dataclass(frozen=True)
class LocalViewItem:
    """Presentation metadata for one peer view inside a single route."""

    view_id: str
    label: str
    description: str = ""


class LocalViewSwitcher(QFrame):
    """Switch between two to five local peer views without route semantics."""

    viewActivated = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("localViewSwitcher")
        self.setAccessibleName(self.tr("Views"))
        self._views: tuple[LocalViewItem, ...] = ()
        self._compact = False
        self._suppress_signal = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.button_row = QWidget(self)
        self.button_layout = QHBoxLayout(self.button_row)
        self.button_layout.setContentsMargins(0, 0, 0, 0)
        self.button_layout.setSpacing(8)
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self.button_group.idClicked.connect(self._on_button_clicked)
        layout.addWidget(self.button_row)

        self.selector = QComboBox(self)
        self.selector.setAccessibleName(self.tr("View"))
        self.selector.currentIndexChanged.connect(self._on_selector_changed)
        self.selector.hide()
        layout.addWidget(self.selector)

    def set_views(
        self,
        views: tuple[LocalViewItem, ...] | list[LocalViewItem],
    ) -> None:
        """Replace the bounded local view set."""
        normalized = tuple(views)
        if normalized and not 2 <= len(normalized) <= 5:
            raise ValueError("LocalViewSwitcher requires two to five views")
        view_ids = tuple(view.view_id for view in normalized)
        if any(not view_id for view_id in view_ids) or len(set(view_ids)) != len(view_ids):
            raise ValueError("Local view IDs must be non-empty and unique")

        self._suppress_signal = True
        for button in self.button_group.buttons():
            self.button_group.removeButton(button)
            self.button_layout.removeWidget(button)
            button.deleteLater()
        self.selector.clear()
        self._views = normalized
        for index, view in enumerate(self._views):
            button = QPushButton(view.label, self.button_row)
            button.setCheckable(True)
            button.setAccessibleName(view.label)
            button.setAccessibleDescription(view.description)
            button.setToolTip(view.description or view.label)
            self.button_group.addButton(button, index)
            self.button_layout.addWidget(button)
            self.selector.addItem(view.label, view.view_id)
            self.selector.setItemData(
                index,
                view.description or view.label,
                Qt.ItemDataRole.ToolTipRole,
            )
        self.button_layout.addStretch()
        if self._views:
            first = self.button_group.button(0)
            if first is not None:
                first.setChecked(True)
            self.selector.setCurrentIndex(0)
        self._suppress_signal = False

    def view_ids(self) -> tuple[str, ...]:
        return tuple(view.view_id for view in self._views)

    def active_view_id(self) -> str:
        index = self.selector.currentIndex()
        if 0 <= index < len(self._views):
            return self._views[index].view_id
        return ""

    def set_active_view(self, view_id: str) -> None:
        for index, view in enumerate(self._views):
            if view.view_id != view_id:
                continue
            self._suppress_signal = True
            self.selector.setCurrentIndex(index)
            button = self.button_group.button(index)
            if button is not None:
                button.setChecked(True)
            self._suppress_signal = False
            return

    def set_compact(self, compact: bool) -> None:
        self._compact = bool(compact)
        self.button_row.setVisible(not self._compact)
        self.selector.setVisible(self._compact)

    def is_compact(self) -> bool:
        return self._compact

    def _activate_index(self, index: int) -> None:
        if self._suppress_signal or not 0 <= index < len(self._views):
            return
        self._suppress_signal = True
        self.selector.setCurrentIndex(index)
        button = self.button_group.button(index)
        if button is not None:
            button.setChecked(True)
        self._suppress_signal = False
        self.viewActivated.emit(self._views[index].view_id)

    def _on_button_clicked(self, index: int) -> None:
        self._activate_index(index)

    def _on_selector_changed(self, index: int) -> None:
        self._activate_index(index)
