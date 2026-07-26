"""Deferred background services and favorites policy for MainWindow."""

from __future__ import annotations

# flake8: noqa: F401


import logging
import os
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

from core.navigation import (
    DirectLinkBehavior,
    FedoraVariant,
    NavigationContext,
    NavigationDecision,
    NavigationPolicy,
    NavigationRoute,
    area_for_plugin,
    destinations_for_mode,
    get_destination,
    placement_for_route,
    resolve,
)
from core.plugins import PluginInterface, PluginRegistry
from core.plugins.metadata import CompatStatus, PluginMetadata
from core.plugins.registry import CATEGORY_ICONS
from PyQt6.QtCore import QRect, Qt, QTimer
from PyQt6.QtGui import QKeySequence, QPainter, QShortcut
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QStyledItemDelegate,
    QStyle,
    QStyleOptionViewItem,
    QTabWidget,
    QTreeWidgetItem,
    QTreeWidgetItemIterator,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from services.system import SystemManager  # noqa: F401  (re-exported for legacy callers)
from utils.config_manager import ConfigManager
from utils.favorites import FavoritesManager
from utils.focus_mode import FocusMode
from utils.history import HistoryManager
from utils.log import get_logger
from version import __version__

from ui.icon_pack import get_qicon, icon_tint_variant
from ui.design import semantic_qcolor
from ui.layout_primitives import LayoutMetrics, PageHeader
from ui.lazy_widget import LazyWidget
from ui.navigation import DestinationHost, DestinationSidebar
from ui.main_window_interactions import MainWindowInteractionMixin

if TYPE_CHECKING:
    from core.plugins.spec import PluginSpec

logger = get_logger(__name__)

# Custom data roles for sidebar items
_ROLE_DESC = Qt.ItemDataRole.UserRole + 1  # Tab description string
_ROLE_BADGE = Qt.ItemDataRole.UserRole + 2  # "recommended" | "advanced" | ""
_ROLE_STATUS = Qt.ItemDataRole.UserRole + 3  # "ok" | "warning" | "error" | ""
_ROLE_NAME = Qt.ItemDataRole.UserRole + 4  # Raw tab name (without badges/status)
_ROLE_ICON = Qt.ItemDataRole.UserRole + 5  # Semantic icon token
_ROLE_ROUTE_ID = Qt.ItemDataRole.UserRole + 6  # Stable route/plugin ID
_BADGE_SUFFIXES = {
    "recommended": "  [recommended]",
    "advanced": "  [advanced]",
}




class MainWindowServiceMixin:
    """Deferred services that must never delay meaningful Home."""

    def _start_pulse_listener(self: Any) -> None:
        """Initialize and start the Pulse event listener."""
        try:
            from utils.pulse import PulseThread, SystemPulse

            self.pulse = SystemPulse()
            self.pulse_thread = PulseThread(self.pulse)
            self.pulse.moveToThread(self.pulse_thread)
            self.pulse_thread.start()
        except (RuntimeError, OSError) as e:
            logger.debug("Failed to start pulse listener: %s", e)

    @staticmethod
    def _background_services_enabled() -> bool:
        """Return whether persisted settings require tray/background runtime."""
        try:
            from utils.settings import SettingsManager

            return bool(SettingsManager.instance().get("start_minimized", False))
        except (ImportError, OSError, RuntimeError, TypeError, ValueError):
            return False

    def _initialize_background_services(self: Any) -> None:
        """Start tray and Pulse only for an explicitly background-enabled app."""
        if not self._background_services_enabled():
            return
        self.setup_tray()
        self._start_pulse_listener()

    def _schedule_post_render_services(self: Any) -> None:
        """Record meaningful Home without starting hidden probes or timers."""
        if self._post_render_services_scheduled or self._runtime_cleaned:
            return
        self._post_render_services_scheduled = True

    def _build_favorites_section(self):
        """Compatibility no-op: favorites remain stored outside the v15 sidebar."""
        return

    def _sidebar_context_menu(self, pos):
        """Show context menu for sidebar items with favorite toggle."""
        item = self.sidebar.itemAt(pos)
        if not item or not item.data(0, Qt.ItemDataRole.UserRole):
            return

        from PyQt6.QtWidgets import QMenu

        tab_id = item.data(0, _ROLE_ROUTE_ID)
        if not tab_id:
            tab_name = item.data(0, _ROLE_NAME)
            if not tab_name:
                tab_name = item.text(0)
                for suffix in _BADGE_SUFFIXES.values():
                    tab_name = tab_name.replace(suffix, "")
                tab_name = tab_name.strip()
            route = resolve(str(tab_name))
            tab_id = route.id if route else str(tab_name).lower().replace(" ", "_")
        tab_id = str(tab_id)

        menu = QMenu(self)
        is_fav = FavoritesManager.is_favorite(tab_id)

        if is_fav:
            action = menu.addAction(self.tr("Remove from Favorites"))
        else:
            action = menu.addAction(self.tr("Add to Favorites"))

        result = menu.exec(self.sidebar.mapToGlobal(pos))
        if result == action:
            FavoritesManager.toggle_favorite(tab_id)
            self._rebuild_favorites_section()

    def _rebuild_favorites_section(self):
        """Compatibility no-op while favorites are stored for later surfaces."""
        return

    def _rebuild_sidebar_for_navigation_mode(self, mode=None):
        """Refresh policy and destination rows without rebuilding page widgets."""
        from utils.navigation_mode import NavigationModeManager

        mode = mode or NavigationModeManager.get_mode()
        previous_route = self._active_route_id
        self._active_navigation_mode = mode
        self._navigation_context = replace(self._navigation_context, mode=mode)
        self.sidebar.set_destinations(destinations_for_mode(mode))
        self._active_destination_id = ""
        if previous_route and self.switch_to_route(previous_route, record_history=False):
            return
        if self.sidebar.topLevelItemCount() > 0:
            self.sidebar.setCurrentItem(self.sidebar.topLevelItem(0))
