"""Route-navigation and page-header coordination for MainWindow."""

from __future__ import annotations

from typing import Any

from core.navigation import (
    NavigationRoute,
    area_for_plugin,
    get_destination,
    placement_for_route,
    resolve,
)
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget

from utils.log import get_logger

logger = get_logger(__name__)


class MainWindowShellMixin:
    """Keep shell navigation and header presentation out of window assembly."""

    _page_header_action_owner: QWidget | None

    def _sync_destination_shell(self: Any, route_id: str) -> None:
        """Synchronize primary and secondary navigation for a stable route."""
        placement = placement_for_route(route_id)
        if placement is None:
            return
        destination = get_destination(placement.destination_id)
        if destination is None:
            return

        self._selecting_destination = True
        self.sidebar.select_destination(destination.id)
        self._selecting_destination = False

        if destination.id != self._active_destination_id:
            self.destination_host.set_destination(
                destination,
                self._navigation_context,
                route_id,
            )
            self._active_destination_id = destination.id
        else:
            self.destination_host.clear_explanation()
            self.destination_host.set_active_route(route_id)

    def _update_breadcrumb(self: Any, item: Any) -> None:
        """Update the page header from presentation metadata, never route IDs."""
        parent = item.parent()
        category = ""
        if parent:
            category = str(parent.data(0, Qt.ItemDataRole.UserRole + 1) or parent.text(0))
        page_name = item.data(0, Qt.ItemDataRole.UserRole + 4)
        if not page_name:
            page_name = item.text(0)
            for suffix in ("  [recommended]", "  [advanced]"):
                page_name = page_name.replace(suffix, "")
        page_name = str(page_name)
        description = str(item.data(0, Qt.ItemDataRole.UserRole + 1) or "")
        route = resolve(
            self._active_route_id
            or str(item.data(0, Qt.ItemDataRole.UserRole + 6) or "")
        )
        if route:
            area = area_for_plugin(route.plugin_id)
            category = area.label if area else route.category
            page_name = route.label
            description = route.description

        self._bc_category.setText(category)
        self._bc_page.setText(page_name)
        self._bc_desc.setText(description)
        self._breadcrumb_frame.set_content(category, page_name, description)
        self._bc_parent_item = parent

    def _update_header_for_route(
        self: Any,
        route: NavigationRoute,
        entry: Any | None = None,
    ) -> None:
        """Render the focused header when a route has no visible sidebar row."""
        placement = placement_for_route(route.id)
        destination = (
            get_destination(placement.destination_id)
            if placement is not None
            else None
        )
        area = area_for_plugin(route.plugin_id)
        category = (
            destination.label
            if destination
            else (area.label if area else route.category)
        )
        self._bc_category.setText(category)
        self._bc_page.setText(route.label)
        self._bc_desc.setText(route.description)
        self._breadcrumb_frame.set_content(category, route.label, route.description)
        self._bc_parent_item = (
            entry.tree_item.parent()
            if entry and entry.tree_item
            else None
        )

    def _sync_page_header_actions(
        self: Any,
        route: NavigationRoute | None,
    ) -> None:
        """Populate the shell header from an optional route-owned provider."""
        header = getattr(self, "_breadcrumb_frame", None)
        clear_actions = getattr(header, "clear_actions", None)
        widget: QWidget | None = None
        actions: tuple[object, ...] = ()
        if route is not None:
            entry = self._sidebar_index.get(route.plugin_id)
            if entry is not None:
                widget = self._real_widget_for_entry(entry)
                provider = getattr(widget, "page_header_actions", None)
                if callable(provider):
                    try:
                        actions = tuple(provider(route))
                    except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
                        logger.debug(
                            "Page header actions failed for %s: %s",
                            route.id,
                            exc,
                        )

        if getattr(self, "_page_header_action_owner", None) is None and not actions:
            return
        if callable(clear_actions):
            clear_actions()
        self._page_header_action_owner = None
        if not actions:
            return
        add_action = getattr(header, "add_action", None)
        if not callable(add_action):
            return
        for action in actions:
            control = action
            primary = False
            if isinstance(action, tuple) and len(action) == 2:
                control, primary = action
            if isinstance(control, QWidget):
                add_action(control, primary=bool(primary))
        self._page_header_action_owner = widget
