"""Presentation-only responsive section navigation."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QEvent, QRect, QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QFrame, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

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
