"""Flat primary destination navigation for the v15 application shell."""

from __future__ import annotations

from collections.abc import Iterable

from core.navigation.models import Destination
from core.navigation.routes import ShellRoute, all_shell_routes, visible_shell_routes
from PyQt6.QtCore import QEvent, QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem

from ui.icon_pack import get_qicon, icon_tint_variant


DESTINATION_ID_ROLE = Qt.ItemDataRole.UserRole + 20
DESTINATION_LABEL_ROLE = Qt.ItemDataRole.UserRole + 21
DESTINATION_ICON_ROLE = Qt.ItemDataRole.UserRole + 22
DESTINATION_GROUP_ROLE = Qt.ItemDataRole.UserRole + 23

_PRESENTATION_GROUPS = {
    "home": "Overview",
    "software_updates": "Manage",
    "system": "Manage",
    "network_security": "Manage",
    "changes": "Review",
}


# The shell navigation model lives in ``core.navigation.routes``; this alias
# keeps the name used by the sidebar and its callers.
UtilityDestination = ShellRoute

UTILITY_DESTINATIONS: tuple[UtilityDestination, ...] = visible_shell_routes(False)


class DestinationSidebar(QTreeWidget):
    """Keyboard-accessible flat list of stable shell destinations."""

    destinationActivated = pyqtSignal(str)
    toolsToggled = pyqtSignal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._collapsed = False
        self._tools_item: QTreeWidgetItem | None = None
        self.setObjectName("destinationSidebar")
        self.setHeaderHidden(True)
        self.setRootIsDecorated(False)
        self.setIndentation(0)
        self.setUniformRowHeights(True)
        self.setAnimated(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setIconSize(QSize(20, 20))
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(self.tr("Primary navigation"))
        self.currentItemChanged.connect(self._emit_destination)
        self.itemClicked.connect(self._toggle_tools_item)
        self.itemExpanded.connect(self._tools_expanded)
        self.itemCollapsed.connect(self._tools_collapsed)

    def set_destinations(self, destinations: Iterable[Destination]) -> None:
        """Replace rows with the supplied destination definitions."""
        selected = self.current_destination_id()
        self.clear()
        minimum_height = max(40, int(self.fontMetrics().height() * 2.35))
        previous_group = ""
        for destination in destinations:
            group = _PRESENTATION_GROUPS.get(destination.id, self.tr("Other"))
            item = QTreeWidgetItem(self)
            item.setData(0, DESTINATION_ID_ROLE, destination.id)
            item.setData(0, DESTINATION_LABEL_ROLE, destination.label)
            item.setData(0, DESTINATION_ICON_ROLE, destination.icon)
            item.setData(0, DESTINATION_GROUP_ROLE, group)
            item.setData(
                0,
                Qt.ItemDataRole.AccessibleTextRole,
                destination.label,
            )
            item.setData(
                0,
                Qt.ItemDataRole.AccessibleDescriptionRole,
                self.tr("%1 group. Open %2").replace("%1", group).replace("%2", destination.label),
            )
            item.setText(0, "" if self._collapsed else destination.label)
            item.setToolTip(0, destination.label)
            group_spacing = 8 if previous_group and group != previous_group else 0
            item.setSizeHint(0, QSize(0, minimum_height + group_spacing))
            item.setIcon(
                0,
                get_qicon(
                    destination.icon,
                    size=20,
                    tint=icon_tint_variant(destination.icon, selected=False),
                ),
            )
            previous_group = group
        if selected:
            self.select_destination(selected)

    def set_utility_destinations(
        self,
        destinations: Iterable[UtilityDestination] = UTILITY_DESTINATIONS,
    ) -> None:
        """Render primary destinations and one explicit expandable Tools group."""
        definitions = tuple(destinations)
        selected = self.current_destination_id()
        expanded = any(route.advanced for route in definitions)
        was_blocked = self.blockSignals(True)
        try:
            self.clear()
            self._tools_item = None
            self.setIndentation(12)
            for destination in definitions:
                if not destination.advanced:
                    self._add_utility_item(destination, self)
            tools = QTreeWidgetItem(self)
            self._tools_item = tools
            tools.setData(0, DESTINATION_LABEL_ROLE, self.tr("Tools"))
            tools.setData(0, DESTINATION_ICON_ROLE, "developer-tools")
            tools.setData(0, Qt.ItemDataRole.AccessibleTextRole, self.tr("Tools"))
            tools.setToolTip(0, self.tr("Expand or collapse System, Storage, Network, Security, and Logs"))
            tools.setSizeHint(0, QSize(0, max(44, self.fontMetrics().height() * 2)))
            tools.setIcon(0, get_qicon("developer-tools", size=20))
            tools.setText(0, "" if self._collapsed else self.tr("Tools") + ("  ▾" if expanded else "  ▸"))
            for route in all_shell_routes():
                if route.advanced:
                    self._add_utility_item(route, tools)
            tools.setExpanded(expanded)
            if selected:
                for item in self._destination_items():
                    if item.data(0, DESTINATION_ID_ROLE) == selected and (item.parent() is None or expanded):
                        self.setCurrentItem(item)
                        break
        finally:
            self.blockSignals(was_blocked)

    def _add_utility_item(self, route: UtilityDestination, parent) -> None:
        item = QTreeWidgetItem(parent)
        item.setData(0, DESTINATION_ID_ROLE, route.id)
        item.setData(0, DESTINATION_LABEL_ROLE, self.tr(route.label))
        item.setData(0, DESTINATION_ICON_ROLE, route.icon)
        item.setData(0, DESTINATION_GROUP_ROLE, self.tr("Tools") if route.advanced else self.tr("Main tasks"))
        item.setData(0, Qt.ItemDataRole.AccessibleTextRole, self.tr(route.label))
        item.setData(0, Qt.ItemDataRole.AccessibleDescriptionRole, self.tr(route.description))
        item.setText(0, "" if self._collapsed else self.tr(route.label))
        item.setToolTip(0, self.tr(route.label))
        item.setSizeHint(0, QSize(0, max(44, int(self.fontMetrics().height() * 2.35))))
        item.setIcon(0, get_qicon(route.icon, size=20, tint=icon_tint_variant(route.icon, selected=False)))

    def _destination_items(self):
        for index in range(self.topLevelItemCount()):
            item = self.topLevelItem(index)
            if item is None:
                continue
            yield item
            for child_index in range(item.childCount()):
                child = item.child(child_index)
                if child is not None:
                    yield child

    def _toggle_tools_item(self, item, _column: int) -> None:
        if item is self._tools_item:
            item.setExpanded(not item.isExpanded())

    def _tools_expanded(self, item) -> None:
        if item is self._tools_item:
            item.setText(0, "" if self._collapsed else self.tr("Tools") + "  ▾")
            item.setData(0, Qt.ItemDataRole.AccessibleDescriptionRole, self.tr("Tools expanded. Press Space to collapse."))
            self.toolsToggled.emit(True)

    def _tools_collapsed(self, item) -> None:
        if item is self._tools_item:
            item.setText(0, "" if self._collapsed else self.tr("Tools") + "  ▸")
            item.setData(0, Qt.ItemDataRole.AccessibleDescriptionRole, self.tr("Tools collapsed. Press Space to expand."))
            self.toolsToggled.emit(False)

    def keyPressEvent(self, event) -> None:
        if self.currentItem() is self._tools_item and event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._toggle_tools_item(self._tools_item, 0)
            event.accept()
            return
        super().keyPressEvent(event)

    def changeEvent(self, event) -> None:
        if event is not None and event.type() == QEvent.Type.FontChange:
            self._refresh_row_sizes()
        super().changeEvent(event)

    def destination_ids(self) -> tuple[str, ...]:
        """Return visible destinations, excluding the Tools disclosure itself."""
        return tuple(
            str(item.data(0, DESTINATION_ID_ROLE)) for item in self._destination_items()
            if item.data(0, DESTINATION_ID_ROLE) and (item.parent() is None or item.parent().isExpanded())
        )

    def current_destination_id(self) -> str:
        item = self.currentItem()
        if item is None:
            return ""
        return str(item.data(0, DESTINATION_ID_ROLE) or "")

    def presentation_groups(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        """Return visual grouping without creating navigation identifiers."""
        groups: list[tuple[str, list[str]]] = []
        for item in self._destination_items():
            if not item.data(0, DESTINATION_ID_ROLE) or (item.parent() is not None and not item.parent().isExpanded()):
                continue
            group = str(item.data(0, DESTINATION_GROUP_ROLE) or "")
            destination_id = str(item.data(0, DESTINATION_ID_ROLE) or "")
            if not groups or groups[-1][0] != group:
                groups.append((group, []))
            groups[-1][1].append(destination_id)
        return tuple((group, tuple(ids)) for group, ids in groups)

    def select_destination(self, destination_id: str) -> bool:
        """Select a destination by stable ID."""
        for item in self._destination_items():
            if item.data(0, DESTINATION_ID_ROLE) == destination_id:
                if item.parent() is not None:
                    item.parent().setExpanded(True)
                self.setCurrentItem(item)
                return True
        return False

    def set_collapsed(self, collapsed: bool) -> None:
        """Render icon-only rows while preserving labels as tooltips."""
        self._collapsed = bool(collapsed)
        self.setProperty("collapsed", self._collapsed)
        for item in self._destination_items():
            label = str(item.data(0, DESTINATION_LABEL_ROLE) or "")
            if item is self._tools_item:
                label += "  ▾" if item.isExpanded() else "  ▸"
            item.setText(0, "" if self._collapsed else label)
            item.setToolTip(0, label)
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)

    def _refresh_row_sizes(self) -> None:
        minimum_height = max(44, int(self.fontMetrics().height() * 2.35))
        for item in self._destination_items():
            if item is not None:
                item.setSizeHint(0, QSize(0, minimum_height))

    def refresh_icon_tints(self) -> None:
        """Rebuild icon colours after a live semantic theme change."""
        selected = self.current_destination_id()
        for item in self._destination_items():
            icon_name = str(item.data(0, DESTINATION_ICON_ROLE) or "")
            if not icon_name:
                continue
            item.setIcon(
                0,
                get_qicon(
                    icon_name,
                    size=20,
                    tint=icon_tint_variant(
                        icon_name,
                        selected=item.data(0, DESTINATION_ID_ROLE) == selected,
                    ),
                ),
            )

    def _emit_destination(self, current, previous) -> None:
        del previous
        if current is None:
            return
        destination_id = str(current.data(0, DESTINATION_ID_ROLE) or "")
        if destination_id:
            self.destinationActivated.emit(destination_id)
