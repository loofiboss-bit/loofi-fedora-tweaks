"""Route-navigation and page-header coordination for MainWindow."""

from __future__ import annotations

from typing import Any

from core.navigation import (
    NavigationRoute,
    area_for_plugin,
    destinations_for_mode,
    get_destination,
    placement_for_route,
    resolve,
)
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget

from utils.log import get_logger
from ui.presentation import visible_label

logger = get_logger(__name__)


class MainWindowShellMixin:
    """Keep shell navigation and header presentation out of window assembly."""

    _page_header_action_owner: QWidget | None

    def _sync_destination_shell(self: Any, route_id: str) -> None:
        """Synchronize primary and secondary navigation for a stable route."""
        utility_destination_for_route = getattr(
            self,
            "_utility_destination_for_route",
            lambda _route_id: "",
        )
        utility_destination_id = utility_destination_for_route(route_id)
        utility_ready = bool(getattr(self, "_utility_shell_ready", False))
        if utility_ready and utility_destination_id:
            # v29 keeps primary navigation at user jobs.  Detailed routes
            # still resolve through the core policy but never create a second
            # competing destination rail.
            self._selecting_destination = True
            try:
                self.sidebar.select_destination(utility_destination_id)
            finally:
                self._selecting_destination = False
            self.destination_host.clear_explanation()
            self.destination_host.hide()
            self._active_destination_id = utility_destination_id
            return

        route = resolve(str(route_id))
        if utility_ready and route is not None and (
            route.id == "activity"
            or route.plugin_id == "activity"
            or route.id == "settings"
            or route.plugin_id == "settings"
        ):
            # Activity & Recovery and Settings are header-owned secondary
            # surfaces; they should not leave a stale primary selection.
            self._selecting_destination = True
            try:
                self.sidebar.clearSelection()
                self.sidebar.setCurrentItem(None)
            finally:
                self._selecting_destination = False
            self.destination_host.clear_explanation()
            self.destination_host.hide()
            self._active_destination_id = ""
            return

        placement = placement_for_route(route_id)
        if placement is None:
            return
        destination = get_destination(placement.destination_id)
        if destination is None:
            return

        # Settings is intentionally opened from the header gear instead of
        # becoming a sixth primary destination.  Clear the primary selection
        # and hide its secondary rail while the settings page is active;
        # otherwise the previous destination (usually Changes) remains
        # visually selected even though the content has changed.
        primary_ids = {
            item.id
            for item in destinations_for_mode(
                getattr(self, "_active_navigation_mode", None)
            )
        }
        if destination.id not in primary_ids:
            self._selecting_destination = True
            try:
                self.sidebar.clearSelection()
                self.sidebar.setCurrentItem(None)
            finally:
                self._selecting_destination = False
            self.destination_host.clear_explanation()
            self.destination_host.hide()
            self._active_destination_id = ""
            return

        self._selecting_destination = True
        self.sidebar.select_destination(destination.id)
        self._selecting_destination = False
        # Settings hides the secondary destination rail; restore it when the
        # user returns to any primary destination from the sidebar or search.
        self.destination_host.show()

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

        category = visible_label(category)
        page_name = visible_label(page_name)
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
        utility_ready = bool(getattr(self, "_utility_shell_ready", False))
        if utility_ready and (route.id == "activity" or route.plugin_id == "activity"):
            category = "Activity & Recovery"
        elif utility_ready and (route.id == "settings" or route.plugin_id == "settings"):
            category = "Settings"
        else:
            category = (
                destination.label
                if destination
                else (area.label if area else route.category)
            )
        category = visible_label(category)
        page_name = visible_label(route.label)
        self._bc_category.setText(category)
        self._bc_page.setText(page_name)
        self._bc_desc.setText(route.description)
        self._breadcrumb_frame.set_content(category, page_name, route.description)
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
