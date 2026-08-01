"""Interaction, responsive-shell, tray, and theme services for MainWindow."""

from __future__ import annotations
import typing

# flake8: noqa: F401


import logging
import os
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from core.plugins.spec import PluginSpec
    from PyQt6.QtWidgets import QSystemTrayIcon
    from ui.notification_toast import NotificationToast

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


class MainWindowInteractionMixin:
    """Behavioral shell mixin kept separate from route/page construction."""

    tray_icon: QSystemTrayIcon | None
    _toast_widget: NotificationToast | None

    def _setup_command_palette_shortcut(self: typing.Any) -> typing.Any:
        """Compatibility name for registering both global-search shortcuts."""
        self._setup_global_search_shortcuts()

    def _setup_global_search_shortcuts(self: typing.Any) -> None:
        """Bind route/settings search and action search to the same dialog."""
        global_shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        global_shortcut.activated.connect(lambda: self._show_global_search(actions_only=False))
        action_shortcut = QShortcut(QKeySequence("Ctrl+Shift+K"), self)
        action_shortcut.activated.connect(lambda: self._show_global_search(actions_only=True))
        self._global_search_shortcuts = (global_shortcut, action_shortcut)

    def _show_command_palette(self: typing.Any) -> typing.Any:
        """Compatibility entry point for the shared global search."""
        self._show_global_search(actions_only=False)

    def _setup_quick_actions(self: typing.Any) -> typing.Any:
        """Compatibility no-op; action discovery uses global search shortcuts."""

    def _show_quick_actions(self: typing.Any) -> typing.Any:
        """Compatibility entry point for action-filtered global search."""
        self._show_global_search(actions_only=True)

    def _show_global_search(self: typing.Any, *, actions_only: bool = False) -> None:
        """Show the single policy-backed global discovery surface."""
        try:
            from core.navigation import GlobalSearchModel, SearchFilter
            from ui.global_search import GlobalSearchDialog
            from utils.quick_actions_config import QuickActionsConfig

            context = getattr(self, "_navigation_context", NavigationContext())
            model = GlobalSearchModel(
                context,
                configured_quick_actions=QuickActionsConfig.get_actions(),
            )
            dialog = GlobalSearchDialog(
                model,
                self._activate_global_search_result,
                search_filter=(SearchFilter.ACTIONS if actions_only else SearchFilter.ALL),
                parent=self,
            )
            dialog.exec()
        except ImportError:
            logger.debug("Global search module not available", exc_info=True)

    def _activate_global_search_result(self: typing.Any, result: typing.Any) -> bool:
        """Navigate to a result and optionally preselect an Action Center item."""
        route_id = str(getattr(result, "route_id", "") or "")
        if not route_id or not self.switch_to_route(route_id):
            return False
        action_id = str(getattr(result, "action_id", "") or "")
        if action_id:
            self._preselect_action_center(action_id)
        return True

    def _preselect_action_center(
        self: typing.Any,
        action_id: str,
        parameters: typing.Any = None,
        finding_context: typing.Any = None,
    ) -> bool:
        """Select an Action Center candidate without planning or running it."""
        entry = self._sidebar_index.get("maintenance")
        if entry is None:
            return False
        widget = self._real_widget_for_entry(entry)
        preselect = getattr(widget, "preselect_action", None)
        if not callable(preselect):
            return False
        if finding_context is not None:
            return bool(
                preselect(
                    action_id,
                    parameters,
                    finding_context=finding_context,
                )
            )
        if parameters is None:
            return bool(preselect(action_id))
        return bool(preselect(action_id, parameters))

    def _toggle_sidebar(self: typing.Any) -> typing.Any:
        """Toggle sidebar between expanded and collapsed states."""
        self._auto_sidebar_collapsed = False
        self._set_sidebar_collapsed(not self._sidebar_collapsed)

    def _set_sidebar_toggle_state(self: typing.Any, collapsed: bool) -> None:
        """Present a panel control that cannot be mistaken for Back."""
        action = (
            self.tr("Expand navigation sidebar")
            if collapsed
            else self.tr("Collapse navigation sidebar")
        )
        standard_pixmaps = QStyle.StandardPixmap
        standard_icon = (
            getattr(
                standard_pixmaps,
                "SP_TitleBarUnshadeButton",
                standard_pixmaps.SP_ArrowRight,
            )
            if collapsed
            else getattr(
                standard_pixmaps,
                "SP_TitleBarShadeButton",
                standard_pixmaps.SP_ArrowLeft,
            )
        )
        self._sidebar_toggle.setText("" if collapsed else self.tr("Collapse"))
        tool_button_style = getattr(Qt, "ToolButtonStyle", None)
        if tool_button_style is not None:
            self._sidebar_toggle.setToolButtonStyle(
                tool_button_style.ToolButtonIconOnly
                if collapsed
                else tool_button_style.ToolButtonTextBesideIcon
            )
        self._sidebar_toggle.setFixedWidth(
            36 if collapsed else max(104, int(self._line_height * 6.5))
        )
        style = self.style()
        if style is not None:
            self._sidebar_toggle.setIcon(style.standardIcon(standard_icon))
        self._sidebar_toggle.setToolTip(action)
        self._sidebar_toggle.setAccessibleName(action)

    def _set_sidebar_collapsed(self: typing.Any, collapsed: bool) -> None:
        """Apply sidebar collapsed/expanded state without changing route data."""
        if not collapsed:
            self._sidebar_container.setFixedWidth(self._sidebar_expanded_width)
            self._sidebar_layout.setContentsMargins(12, 14, 12, 10)
            self.sidebar.setVisible(True)
            self._set_sidebar_icon_only(False)
            self._global_search_button.setText(self.tr("Search  Ctrl+K"))
            self._set_sidebar_toggle_state(False)
            self._sidebar_collapsed = False
        else:
            collapsed_width = getattr(getattr(self, "_metrics", None), "sidebar_collapsed_width", int(self._line_height * 4))
            self._sidebar_container.setFixedWidth(collapsed_width)
            self._sidebar_layout.setContentsMargins(8, 14, 8, 10)
            self.sidebar.setVisible(True)
            self._set_sidebar_icon_only(True)
            self._global_search_button.setText("")
            self._set_sidebar_toggle_state(True)
            self._sidebar_collapsed = True

    def _set_section_navigation_compact(self: typing.Any, compact: bool) -> None:
        """Move section navigation above content at the minimum layout."""
        compact = bool(compact)
        if compact == getattr(self, "_section_navigation_compact", None):
            set_compact = getattr(self.destination_host, "set_compact", None)
            if callable(set_compact):
                set_compact(compact)
            return
        self._shell_body_layout.removeWidget(self.destination_host)
        self._shell_body_layout.removeWidget(self.content_area)
        if compact:
            self._shell_body_layout.addWidget(self.destination_host, 0, 0, 1, 2)
            self._shell_body_layout.addWidget(self.content_area, 1, 0, 1, 2)
            self._shell_body_layout.setColumnStretch(0, 1)
            self._shell_body_layout.setColumnStretch(1, 0)
        else:
            self._shell_body_layout.addWidget(self.destination_host, 0, 0)
            self._shell_body_layout.addWidget(self.content_area, 0, 1)
            self._shell_body_layout.setColumnStretch(0, 0)
            self._shell_body_layout.setColumnStretch(1, 1)
        set_compact = getattr(self.destination_host, "set_compact", None)
        if callable(set_compact):
            set_compact(compact)
        self._section_navigation_compact = compact

    def _apply_responsive_shell(self: typing.Any, width: int) -> None:
        """Apply the v16 wide, medium, and minimum shell breakpoints."""
        compact_sections = width < 900
        self._set_section_navigation_compact(compact_sections)
        if width < 1180 and not self._sidebar_collapsed:
            self._auto_sidebar_collapsed = True
            self._set_sidebar_collapsed(True)
        elif width >= 1180 and self._auto_sidebar_collapsed:
            self._auto_sidebar_collapsed = False
            self._set_sidebar_collapsed(False)

    def resizeEvent(self: typing.Any, event: typing.Any) -> None:
        """Apply responsive sidebar breakpoints as the window changes size."""
        try:
            width = int(self.width())
            self._apply_responsive_shell(width)
        except (TypeError, ValueError, AttributeError, RuntimeError):
            logger.debug("Responsive sidebar resize update failed", exc_info=True)
        QMainWindow.resizeEvent(self, event)

    def _sidebar_display_text(self: typing.Any, item: QTreeWidgetItem) -> str:
        """Return the expanded display text for a sidebar item."""
        name = item.data(0, _ROLE_NAME)
        if name:
            badge = item.data(0, _ROLE_BADGE) or ""
            suffix = _BADGE_SUFFIXES.get(badge, "")
            return f"{name}{suffix}"
        return str(item.data(0, _ROLE_DESC) or item.text(0))

    def _set_sidebar_icon_only(self: typing.Any, collapsed: bool) -> None:
        """Toggle sidebar labels while keeping icon rows selectable."""
        if getattr(self, "_shell_uses_destinations", False) is True:
            self.sidebar.set_collapsed(collapsed)
            return
        iterator = QTreeWidgetItemIterator(self.sidebar)
        while iterator.value():
            item = iterator.value()
            if item is None:
                break
            display_text = self._sidebar_display_text(item)
            if display_text:
                item.setToolTip(0, item.toolTip(0) or display_text)
            item.setText(0, "" if collapsed else display_text)
            iterator += 1

    def _setup_keyboard_shortcuts(self: typing.Any) -> typing.Any:
        """Register destination-aware shell navigation shortcuts."""
        # Ctrl+1 through Ctrl+7 select stable destinations.
        for i in range(1, 8):
            shortcut = QShortcut(QKeySequence(f"Ctrl+{i}"), self)
            shortcut.activated.connect(lambda idx=i - 1: self._select_category(idx))

        # Ctrl+Tab - next tab
        next_tab = QShortcut(QKeySequence("Ctrl+Tab"), self)
        next_tab.activated.connect(self._select_next_item)

        # Ctrl+Shift+Tab - previous tab
        prev_tab = QShortcut(QKeySequence("Ctrl+Shift+Tab"), self)
        prev_tab.activated.connect(self._select_prev_item)

        back = QShortcut(QKeySequence("Alt+Left"), self)
        back.activated.connect(self.navigate_back)
        forward = QShortcut(QKeySequence("Alt+Right"), self)
        forward.activated.connect(self.navigate_forward)

        # Ctrl+Q - Quit
        quit_shortcut = QShortcut(QKeySequence("Ctrl+Q"), self)
        quit_shortcut.activated.connect(self.quit_app)

        # F1 - Show shortcut help
        help_shortcut = QShortcut(QKeySequence("F1"), self)
        help_shortcut.activated.connect(self._show_shortcut_help)

    def _select_category(self: typing.Any, index: int) -> typing.Any:
        """Compatibility name for selecting a flat destination by position."""
        if index < self.sidebar.topLevelItemCount():
            item = self.sidebar.topLevelItem(index)
            self.sidebar.setCurrentItem(item)

    def _select_next_item(self: typing.Any) -> typing.Any:
        current = self.sidebar.currentItem()
        if not current:
            return

        # Try to find next item below
        next_item = self.sidebar.itemBelow(current)
        if next_item:
            self.sidebar.setCurrentItem(next_item)
        else:
            # Wrap around to top
            if self.sidebar.topLevelItemCount() > 0:
                self.sidebar.setCurrentItem(self.sidebar.topLevelItem(0))

    def _select_prev_item(self: typing.Any) -> typing.Any:
        current = self.sidebar.currentItem()
        if not current:
            return

        # Try to find item above
        prev_item = self.sidebar.itemAbove(current)
        if prev_item:
            self.sidebar.setCurrentItem(prev_item)
        else:
            # Wrap around to the last destination.
            self.sidebar.setCurrentItem(self.sidebar.topLevelItem(self.sidebar.topLevelItemCount() - 1))

    def _show_shortcut_help(self: typing.Any) -> typing.Any:
        """Show keyboard shortcuts help dialog."""
        from PyQt6.QtWidgets import QMessageBox

        shortcuts = (
            "Ctrl+K — Search routes, settings, and actions\n"
            "Ctrl+Shift+K — Search actions\n"
            "Ctrl+1..7 — Switch destination\n"
            "Ctrl+Tab — Next destination\n"
            "Ctrl+Shift+Tab — Previous destination\n"
            "Alt+Left/Right — Route history\n"
            "Ctrl+Q — Quit\n"
            "F1 — This help"
        )
        QMessageBox.information(self, self.tr("Keyboard Shortcuts"), shortcuts)

    def show_toast(self: typing.Any, title: str, message: str, category: str = "general") -> typing.Any:
        """Show an animated toast notification at the top-right."""
        try:
            from ui.notification_toast import NotificationToast

            if self._toast_widget is None:
                self._toast_widget = NotificationToast(self)
            self._toast_widget.show_toast(title, message, category)
        except (RuntimeError, ImportError) as e:
            logger.debug("Failed to show toast notification: %s", e)

    def _refresh_status_indicators(self: typing.Any) -> typing.Any:
        """Update sidebar status indicators from live system data."""
        try:
            # Maintenance: check for updates
            from utils.update_checker import UpdateChecker

            update_info = UpdateChecker.check_for_updates(timeout=5, use_cache=True)
            if update_info and update_info.is_newer:
                self._set_tab_status("maintenance", "warning", "Updates available")
            else:
                self._set_tab_status("maintenance", "ok", "Up to date")
        except (RuntimeError, OSError, ValueError) as e:
            logger.debug("Failed to check for updates: %s", e)
            self._set_tab_status("maintenance", "", "")

        try:
            # Storage: check disk space
            from services.hardware.disk import DiskManager

            usage = DiskManager.get_disk_usage("/")
            if usage and hasattr(usage, "percent_used"):
                if usage.percent_used >= 90:
                    self._set_tab_status("storage", "error", f"Disk {usage.percent_used:.0f}% full")
                elif usage.percent_used >= 75:
                    self._set_tab_status("storage", "warning", f"Disk {usage.percent_used:.0f}% used")
                else:
                    self._set_tab_status("storage", "ok", "Healthy")
        except (RuntimeError, OSError, ValueError) as e:
            logger.debug("Failed to check disk space: %s", e)
            self._set_tab_status("storage", "", "")

    def _set_tab_status(self: typing.Any, tab_id: str, status: str, tooltip: str = "") -> typing.Any:
        """Set a colored status indicator on a sidebar tab by plugin ID. O(1) lookup."""
        entry = self._sidebar_index.get(tab_id)
        if not entry:
            logger.debug("_set_tab_status: unknown tab_id %s", tab_id)
            return

        entry.status = status
        if entry.tree_item is None:
            return
        entry.tree_item.setData(0, _ROLE_STATUS, status)

        if tooltip:
            desc = entry.metadata.description or ""
            entry.tree_item.setToolTip(0, f"{desc}\n[{tooltip}]" if desc else tooltip)

    def apply_navigation_mode(self: typing.Any, mode: typing.Any = None) -> typing.Any:
        """Apply the canonical Standard/Advanced navigation mode."""
        try:
            from utils.navigation_mode import NavigationModeManager

            if mode is None:
                mode = NavigationModeManager.get_mode()
            if getattr(self, "_active_navigation_mode", None) == mode:
                return
            self._rebuild_sidebar_for_navigation_mode(mode)
        except (ImportError, AttributeError, ValueError, RuntimeError) as e:
            logger.debug("Navigation mode refresh unavailable: %s", e)

    def _check_first_run(self: typing.Any) -> typing.Any:
        """Show the single welcome surface only when its sentinel is absent."""
        try:
            from ui.wizard import FirstRunWelcome, needs_first_run

            welcome = None
            if needs_first_run():
                welcome = FirstRunWelcome(self)
                welcome.exec()
            self.apply_navigation_mode()
            requested_route = str(getattr(welcome, "requested_route", "") or "")
            if requested_route:
                self.switch_to_route(requested_route)
        except ImportError:
            logger.debug("First-run welcome module not available", exc_info=True)

    def setup_tray(self: typing.Any) -> typing.Any:
        from PyQt6.QtGui import QAction, QIcon
        from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon = QSystemTrayIcon(self)
            icon_path = os.path.join(os.path.dirname(__file__), "..", "assets", "loofi-fedora-tweaks.png")
            if os.path.exists(icon_path):
                self.tray_icon.setIcon(QIcon(icon_path))
            else:
                self.tray_icon.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon))

            tray_menu = QMenu()
            show_action = QAction(self.tr("Show"), self)
            show_action.triggered.connect(self.show)

            # Focus Mode toggle
            self.focus_action = QAction(self.tr("Focus Mode"), self)
            self.focus_action.setCheckable(True)
            self.focus_action.setChecked(FocusMode.is_active())
            self.focus_action.triggered.connect(self._toggle_focus_mode)

            quit_action = QAction(self.tr("Quit"), self)
            quit_action.triggered.connect(self.quit_app)

            tray_menu.addAction(show_action)
            tray_menu.addSeparator()
            tray_menu.addAction(self.focus_action)
            tray_menu.addSeparator()
            tray_menu.addAction(quit_action)
            self.tray_icon.setContextMenu(tray_menu)
            self.tray_icon.show()
        else:
            self.tray_icon = None

    def _toggle_focus_mode(self: typing.Any) -> typing.Any:
        """Toggle Focus Mode from tray."""
        result = FocusMode.toggle()
        self.focus_action.setChecked(FocusMode.is_active())

        if self.tray_icon:
            message = result.get("message", "Focus Mode toggled")
            self.tray_icon.showMessage(
                self.tr("Focus Mode"),
                message,
                self.tray_icon.MessageIcon.Information,
                2000,
            )

    def quit_app(self: typing.Any) -> typing.Any:
        self._request_runtime_shutdown()
        from PyQt6.QtWidgets import QApplication

        QApplication.quit()

    def _request_runtime_shutdown(self: typing.Any) -> None:
        """Use the process runtime when present, with a direct test fallback."""
        runtime = getattr(self, "__dict__", {}).get("_runtime")
        shutdown = getattr(runtime, "shutdown", None)
        if callable(shutdown):
            # QObject-owned timers and widgets must be stopped on the GUI
            # thread before ApplicationRuntime invokes its bounded hooks.
            self._request_runtime_stop()
            shutdown()
            return
        self._cleanup_runtime(5.0)

    def _cleanup_runtime(self: typing.Any, timeout: float) -> None:
        """Backward-compatible direct cleanup for tests without a runtime."""
        self._request_runtime_stop()
        self._wait_for_runtime_stop(timeout)

    def _request_runtime_stop(self: typing.Any) -> None:
        """Request window-owned timers, workers, plugins, and Pulse to stop."""
        attributes = getattr(self, "__dict__", {})
        if attributes.get("_runtime_cleaned", False):
            return
        self._runtime_cleaned = True
        self._set_active_plugin("")

        status_timer = getattr(self, "_status_timer", None)
        if status_timer is not None:
            status_timer.stop()
            self._status_timer = None

        registry = PluginRegistry.instance()
        list_all: typing.Callable[[], typing.Iterable[typing.Any]] = getattr(
            registry,
            "list_all",
            lambda: [],
        )
        plugins = list(list_all())
        if not plugins:
            plugins = [
                entry.page_widget
                for entry in getattr(self, "_sidebar_index", {}).values()
            ]
        for plugin in plugins:
            cleanup = getattr(plugin, "cleanup", None)
            if callable(cleanup):
                try:
                    cleanup()
                except (RuntimeError, OSError, TypeError, ValueError) as exc:
                    logger.debug("Failed to cleanup page on close: %s", exc)

        pulse_thread = getattr(self, "pulse_thread", None)
        if pulse_thread:
            try:
                pulse_thread.stop(timeout_ms=0)
            except TypeError:
                pulse_thread.stop()

        tray_icon = getattr(self, "tray_icon", None)
        if tray_icon:
            tray_icon.hide()

    def _wait_for_runtime_stop(self: typing.Any, timeout: float) -> bool:
        """Wait within the runtime's remaining budget for the Pulse thread."""
        pulse_thread = getattr(self, "pulse_thread", None)
        if not pulse_thread:
            return True
        timeout_ms = max(0, min(5000, int(timeout * 1000)))
        wait_for_thread = getattr(pulse_thread, "wait", None)
        if not callable(wait_for_thread):
            return True
        stopped = wait_for_thread(timeout_ms)
        return stopped is not False

    def closeEvent(self: typing.Any, event: typing.Any) -> typing.Any:
        tray_icon = getattr(self, "tray_icon", None)
        if tray_icon and tray_icon.isVisible():
            self.hide()
            tray_icon.showMessage(
                self.tr("Loofi Fedora Tweaks"),
                self.tr("Minimized to tray."),
                tray_icon.MessageIcon.Information,
                2000,
            )
            event.ignore()
        else:
            self._request_runtime_shutdown()
            event.accept()

    def check_dependencies(self: typing.Any) -> typing.Any:
        from services.system.system import cached_which

        critical = ["dnf", "pkexec"]
        missing = [tool for tool in critical if not cached_which(tool)]
        if missing:
            self.show_doctor()

    def show_doctor(self: typing.Any) -> typing.Any:
        from ui.doctor import DependencyDoctor

        doctor = DependencyDoctor(self)
        doctor.actionCenterRequested.connect(self._open_action_center_request)
        doctor.exec()

    # ==================== Theme Management ====================

    def load_theme(self: typing.Any, name: str = "system") -> None:
        """
        Apply invariant component structure with the requested semantic palette.

        System mode derives colours from ``QPalette`` while retaining the same
        card, state, navigation, control, and focus geometry as explicit themes.
        """
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if not isinstance(app, QApplication):
            return
        from ui.design import ThemeManager

        if ThemeManager().apply(app, name):
            sidebar = getattr(self, "sidebar", None)
            refresh_destination_icons = getattr(sidebar, "refresh_icon_tints", None)
            if callable(refresh_destination_icons):
                refresh_destination_icons()
            if sidebar is not None and not callable(refresh_destination_icons):
                self._refresh_sidebar_icon_tints()
            refresh_section_icons = getattr(
                getattr(self, "destination_host", None),
                "refresh_icon_tints",
                None,
            )
            if callable(refresh_section_icons):
                refresh_section_icons()
            self.update()

    @staticmethod
    def detect_system_theme() -> str:
        """
        Detect the system colour-scheme preference via
        ``gsettings`` (GNOME / GTK) and return ``"dark"`` or ``"light"``.

        Returns ``"dark"`` when detection fails.
        """
        from services.desktop import DesktopUtils

        return DesktopUtils.detect_color_scheme()
