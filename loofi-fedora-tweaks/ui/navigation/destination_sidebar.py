"""Flat primary destination navigation for the v15 application shell."""

from __future__ import annotations

from collections.abc import Iterable

from core.navigation.models import Destination
from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem

from ui.icon_pack import get_qicon, icon_tint_variant


DESTINATION_ID_ROLE = Qt.ItemDataRole.UserRole + 20
DESTINATION_LABEL_ROLE = Qt.ItemDataRole.UserRole + 21
DESTINATION_ICON_ROLE = Qt.ItemDataRole.UserRole + 22


class DestinationSidebar(QTreeWidget):
    """Keyboard-accessible flat list of stable shell destinations."""

    destinationActivated = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._collapsed = False
        self.setObjectName("destinationSidebar")
        self.setHeaderHidden(True)
        self.setRootIsDecorated(False)
        self.setIndentation(0)
        self.setUniformRowHeights(True)
        self.setAnimated(False)
        self.setIconSize(QSize(20, 20))
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(self.tr("Primary navigation"))
        self.currentItemChanged.connect(self._emit_destination)

    def set_destinations(self, destinations: Iterable[Destination]) -> None:
        """Replace rows with the supplied destination definitions."""
        selected = self.current_destination_id()
        self.clear()
        minimum_height = max(40, int(self.fontMetrics().height() * 2.35))
        for destination in destinations:
            item = QTreeWidgetItem(self)
            item.setData(0, DESTINATION_ID_ROLE, destination.id)
            item.setData(0, DESTINATION_LABEL_ROLE, destination.label)
            item.setData(0, DESTINATION_ICON_ROLE, destination.icon)
            item.setText(0, "" if self._collapsed else destination.label)
            item.setToolTip(0, destination.label)
            item.setSizeHint(0, QSize(0, minimum_height))
            item.setIcon(
                0,
                get_qicon(
                    destination.icon,
                    size=20,
                    tint=icon_tint_variant(destination.icon, selected=False),
                ),
            )
        if selected:
            self.select_destination(selected)

    def destination_ids(self) -> tuple[str, ...]:
        """Return displayed destination IDs in visual order."""
        destination_ids: list[str] = []
        for index in range(self.topLevelItemCount()):
            item = self.topLevelItem(index)
            if item is not None:
                destination_ids.append(str(item.data(0, DESTINATION_ID_ROLE)))
        return tuple(destination_ids)

    def current_destination_id(self) -> str:
        item = self.currentItem()
        if item is None:
            return ""
        return str(item.data(0, DESTINATION_ID_ROLE) or "")

    def select_destination(self, destination_id: str) -> bool:
        """Select a destination by stable ID."""
        for index in range(self.topLevelItemCount()):
            item = self.topLevelItem(index)
            if item is not None and item.data(0, DESTINATION_ID_ROLE) == destination_id:
                self.setCurrentItem(item)
                return True
        return False

    def set_collapsed(self, collapsed: bool) -> None:
        """Render icon-only rows while preserving labels as tooltips."""
        self._collapsed = bool(collapsed)
        for index in range(self.topLevelItemCount()):
            item = self.topLevelItem(index)
            if item is None:
                continue
            label = str(item.data(0, DESTINATION_LABEL_ROLE) or "")
            item.setText(0, "" if self._collapsed else label)
            item.setToolTip(0, label)

    def _emit_destination(self, current, previous) -> None:
        del previous
        if current is None:
            return
        destination_id = str(current.data(0, DESTINATION_ID_ROLE) or "")
        if destination_id:
            self.destinationActivated.emit(destination_id)
