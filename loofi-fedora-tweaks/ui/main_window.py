"""
Main Window - v25.0 "Plugin Architecture"
PluginRegistry layout with route-aware sidebar navigation, breadcrumb, and status bar.
"""

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
from PyQt6.QtGui import QColor, QKeySequence, QPainter, QShortcut
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTabWidget,
    QTreeWidgetItem,
    QTreeWidgetItemIterator,
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
from ui.layout_primitives import LayoutMetrics, PageHeader
from ui.lazy_widget import LazyWidget
from ui.navigation import DestinationHost, DestinationSidebar

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


@dataclass
class SidebarEntry:
    """Indexed sidebar tab entry for O(1) lookups by plugin ID."""

    plugin_id: str
    display_name: str
    tree_item: QTreeWidgetItem | None
    page_widget: QWidget
    metadata: PluginMetadata
    status: str = field(default="")
    content_widget: QWidget | None = field(default=None)
    area_id: str = field(default="")
    visible_in_sidebar: bool = field(default=True)


class SidebarItemDelegate(QStyledItemDelegate):
    """Custom delegate that renders status dots on sidebar tab items."""

    _STATUS_COLORS = {
        "ok": QColor(76, 175, 80),  # green
        "warning": QColor(255, 193, 7),  # amber
        "error": QColor(244, 67, 54),  # red
    }

    def paint(self, painter: "QPainter | None", option: QStyleOptionViewItem, index) -> None:
        """Paint the item, adding a colored status dot on the right when status is set."""
        super().paint(painter, option, index)

        if painter is None:
            return

        status = index.data(_ROLE_STATUS)
        if not status or status not in self._STATUS_COLORS:
            return

        color = self._STATUS_COLORS[status]
        dot_size = 8
        x = option.rect.right() - dot_size - 8
        y = option.rect.center().y() - dot_size // 2

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRect(x, y, dot_size, dot_size))
        painter.restore()


class DisabledPluginPage(QWidget):
    """Shown in the content area for plugins that are incompatible with the current system."""

    def __init__(self, meta: PluginMetadata, reason: str):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label = QLabel(f"{meta.name} is not available on this system.\n\n{reason}")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setObjectName("disabledPluginLabel")
        layout.addWidget(label)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Initialize logger for this class
        self.logger = logging.getLogger(__name__)

        # Keep native title-bar decorations enabled.
        # This avoids KDE/Wayland/X11 edge-cases where client content can
        # appear to bleed into the top chrome when frameless/custom hints are used.
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, False)
        self.setWindowFlag(Qt.WindowType.CustomizeWindowHint, False)
        self.setWindowTitle(self.tr("Loofi Fedora Tweaks v%1").replace("%1", __version__))

        # HiDPI/Wayland safety: use Qt device-independent units and derive
        # shell dimensions from the active font and available screen size.
        self._metrics = LayoutMetrics.from_widget(self)
        self._line_height = self._metrics.line_height
        self._apply_initial_geometry()

        # Optional/background services are initialized only when settings require
        # them or after the first meaningful Home render.
        self.pulse = None
        self.pulse_thread = None
        self.tray_icon = None
        self._status_timer = None
        self.notif_panel = None
        self._toast_widget = None
        self._post_render_services_scheduled = False

        # Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main Layout (Horizontal: Sidebar | Content)
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        central_widget.setLayout(main_layout)

        # Sidebar container with compact shell chrome.
        sidebar_container = QWidget()
        sidebar_container.setObjectName("sidebarContainer")
        sidebar_width = self._metrics.sidebar_width
        sidebar_container.setFixedWidth(sidebar_width)
        sidebar_container.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        sidebar_layout = QVBoxLayout(sidebar_container)
        sidebar_layout.setContentsMargins(12, 14, 12, 10)
        sidebar_layout.setSpacing(10)

        sidebar_chrome = QHBoxLayout()
        sidebar_chrome.setContentsMargins(0, 0, 0, 0)
        sidebar_chrome.setSpacing(6)

        # Sidebar collapse toggle
        sidebar_chrome.addStretch()
        self._sidebar_toggle = QPushButton("◀")
        self._sidebar_toggle.setObjectName("sidebarToggle")
        self._sidebar_toggle.setMinimumHeight(int(self._line_height * 2.2))
        self._sidebar_toggle.setToolTip(self.tr("Collapse sidebar"))
        self._sidebar_toggle.clicked.connect(self._toggle_sidebar)
        sidebar_chrome.addWidget(self._sidebar_toggle)
        sidebar_layout.addLayout(sidebar_chrome)

        # Track sidebar expanded width and state
        self._sidebar_container = sidebar_container
        self._sidebar_expanded_width = sidebar_width
        self._sidebar_collapsed = False
        self._auto_sidebar_collapsed = False

        # Flat primary navigation. Existing route IDs remain in the route index,
        # not as expandable child rows.
        self.sidebar = DestinationSidebar()
        self.sidebar.setAccessibleName(self.tr("Navigation destinations"))
        self.sidebar.destinationActivated.connect(self._activate_destination)
        self.sidebar.currentItemChanged.connect(self._on_sidebar_selection_changed)
        self.sidebar.setItemDelegate(SidebarItemDelegate(self.sidebar))
        sidebar_layout.addWidget(self.sidebar)

        main_layout.addWidget(sidebar_container)

        # Right side: breadcrumb + content + status bar
        right_side = QVBoxLayout()
        right_side.setContentsMargins(0, 0, 0, 0)
        right_side.setSpacing(0)

        # Page header (keeps breadcrumb-compatible attributes for callers/tests)
        self._breadcrumb_frame = PageHeader()
        self._breadcrumb_frame.setMinimumHeight(self._metrics.header_height)
        self._bc_category = self._breadcrumb_frame.eyebrow
        self._bc_category.setObjectName("bcCategory")
        self._bc_category.clicked.connect(self._on_breadcrumb_category_click)
        self._bc_sep = QLabel("  ›  ")
        self._bc_sep.setObjectName("bcSep")
        self._bc_page = self._breadcrumb_frame.title
        self._bc_page.setObjectName("bcPage")
        self._bc_desc = self._breadcrumb_frame.description
        self._bc_desc.setObjectName("bcDesc")
        right_side.addWidget(self._breadcrumb_frame)

        self.destination_host = DestinationHost()
        self.destination_host.routeRequested.connect(self.switch_to_route)
        right_side.addWidget(self.destination_host)

        # Content Area
        self.content_area = QStackedWidget()
        right_side.addWidget(self.content_area)

        # Status bar
        self._status_frame = QFrame()
        self._status_frame.setObjectName("statusBar")
        self._status_frame.setMinimumHeight(self._metrics.status_height)
        sb_layout = QHBoxLayout(self._status_frame)
        sb_layout.setContentsMargins(12, 0, 12, 0)
        self._status_label = QLabel("")
        self._status_label.setObjectName("statusText")
        sb_layout.addWidget(self._status_label)

        # Undo button (v38.0)
        self._undo_btn = QPushButton(self.tr("↩ Undo"))
        self._undo_btn.setObjectName("undoButton")
        self._undo_btn.setVisible(False)
        self._undo_btn.setToolTip(self.tr("Undo last action"))
        self._undo_btn.clicked.connect(self._on_undo_clicked)
        sb_layout.addWidget(self._undo_btn)

        sb_layout.addStretch()
        self._status_frame.setVisible(False)
        right_side.addWidget(self._status_frame)

        main_layout.addLayout(right_side)

        # Initialize sidebar index infrastructure
        self._sidebar_index: dict[str, SidebarEntry] = {}
        self._category_items: dict[str, QTreeWidgetItem] = {}
        self._pages_cache: dict[str, QWidget] | None = None
        self._active_route_id = ""
        self._active_plugin_id = ""
        self._active_destination_id = ""
        self._selecting_destination = False
        self._shell_uses_destinations = True
        self._route_history: list[str] = []
        self._route_history_index = -1

        # Build sidebar from PluginRegistry (v25.0 plugin architecture)
        context = {
            "main_window": self,
            "config_manager": ConfigManager,  # class, not instance
            "executor": None,  # populated after executor init
        }
        self._build_sidebar_from_registry(context)

        # Select Home after all lazy route entries are registered.
        if self.sidebar.topLevelItemCount() > 0:
            self.sidebar.setCurrentItem(self.sidebar.topLevelItem(0))

        # Background-only services are conditional on persisted settings.
        self._initialize_background_services()

        # Ctrl+K and Ctrl+Shift+K share one policy-backed discovery surface.
        self._setup_command_palette_shortcut()

        # v13.5 UX Polish - keyboard shortcuts
        self._setup_keyboard_shortcuts()

        # First-run wizard
        self._check_first_run()

    @property
    def pages(self) -> dict[str, QWidget]:
        """Backward-compatible accessor. Returns {display_name: widget} view."""
        if self._pages_cache is None:
            self._pages_cache = {entry.display_name: entry.page_widget for entry in self._sidebar_index.values()}
        return self._pages_cache

    @pages.setter
    def pages(self, value: dict) -> None:
        """Backward-compatible setter. Accepts a plain dict (e.g. in tests) and stores it as the cache."""
        # Always (re)initialize real dicts — avoids _Dummy leaking in from test stubs
        if not isinstance(getattr(self, "_sidebar_index", None), dict):
            self._sidebar_index = {}
        if not isinstance(getattr(self, "_category_items", None), dict):
            self._category_items = {}
        self._pages_cache = value

    def _apply_initial_geometry(self) -> None:
        """Set a responsive initial size using available screen geometry."""
        min_width = 860
        min_height = 560
        self.setMinimumSize(min_width, min_height)

        width = 1440
        height = 900
        try:
            screen = self.screen()
            if screen is not None:
                available = screen.availableGeometry()
                width = int(available.width())
                height = int(available.height())
        except (AttributeError, TypeError, ValueError, RuntimeError):
            width = 1440
            height = 900

        target_width = max(min_width, min(int(width * 0.78), width - 80 if width > 980 else width))
        target_height = max(min_height, min(int(height * 0.78), height - 80 if height > 720 else height))
        self.resize(target_width, target_height)

    def _build_sidebar_from_registry(self, context: dict) -> None:
        """Build the destination shell from specs without importing plugin UI."""
        from core.plugins.compat import CompatibilityDetector
        from core.plugins.loader import PluginLoader
        from utils.navigation_mode import NavigationModeManager

        detector = CompatibilityDetector()
        registry = PluginRegistry.instance()
        self._plugin_context = dict(context)
        if not hasattr(self, "_plugin_loader"):
            self._plugin_loader = PluginLoader(registry=registry, detector=detector)
        self._plugin_loader.register_builtin_specs()

        mode = NavigationModeManager.get_mode()
        favorites = FavoritesManager.get_favorites()
        self._active_navigation_mode = mode

        specs = registry.list_specs()
        incompatible_plugin_ids: set[str] = set()
        for spec in specs:
            meta = spec.metadata()
            compat = detector.check_plugin_compat(dict(spec.compat))
            if not compat.compatible:
                incompatible_plugin_ids.add(spec.id)
            lazy = self._wrap_spec_in_lazy(spec)
            self._add_plugin_page(meta, lazy, compat, visible_in_sidebar=False)

        is_atomic = SystemManager.is_atomic()
        self._navigation_context = NavigationContext(
            mode=mode,
            installed_components=frozenset({"core", "specialist"}),
            fedora_variant=(
                FedoraVariant.ATOMIC if is_atomic else FedoraVariant.TRADITIONAL
            ),
            capabilities=frozenset({"rpm-ostree"} if is_atomic else {"dnf"}),
            incompatible_plugin_ids=frozenset(incompatible_plugin_ids),
            favorite_route_ids=frozenset(favorites),
        )
        self.sidebar.set_destinations(destinations_for_mode(mode))

    def _activate_destination(self, destination_id: str) -> None:
        """Open a destination's policy-approved default route."""
        if self._selecting_destination:
            return
        destination = get_destination(destination_id)
        if destination is None:
            return
        self.switch_to_route(destination.default_route_id)

    def _sync_destination_shell(self, route_id: str) -> None:
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

    def _find_or_create_area(self, plugin_id: str, fallback_category: str) -> QTreeWidgetItem:
        """Find/create a focused sidebar area for a plugin."""
        area = area_for_plugin(plugin_id)
        area_id = area.id if area else fallback_category
        if area_id in self._category_items:
            return self._category_items[area_id]

        label = area.label if area else fallback_category
        icon = area.icon if area else CATEGORY_ICONS.get(fallback_category, "")
        return self._create_area_item(area_id, label, icon)

    def _create_area_item(self, area_id: str, label: str, icon: str) -> QTreeWidgetItem:
        """Create a top-level focused area row in sidebar order."""
        if area_id in self._category_items:
            return self._category_items[area_id]
        category_item = QTreeWidgetItem(self.sidebar)
        category_item.setText(0, label)
        category_item.setData(0, _ROLE_DESC, label)
        category_item.setData(0, _ROLE_ROUTE_ID, area_id)
        category_item.setExpanded(True)
        self._set_tree_item_icon(category_item, icon)
        self._category_items[area_id] = category_item
        return category_item

    def _wrap_in_lazy(self, plugin: PluginInterface) -> LazyWidget:
        """Wrap plugin.create_widget() in LazyWidget for deferred instantiation."""
        return LazyWidget(plugin.create_widget)

    def _wrap_spec_in_lazy(self, spec: "PluginSpec") -> LazyWidget:
        """Create a placeholder whose loader imports exactly one plugin on demand."""

        def load_plugin(plugin_id: str = spec.id) -> QWidget:
            return self._load_plugin_widget(plugin_id)

        return LazyWidget(
            load_plugin,
            loading_text=self.tr("Loading %1...").replace("%1", spec.name),
        )

    def _load_plugin_widget(self, plugin_id: str) -> QWidget:
        """Import, construct, and cache one plugin when its route is activated."""
        widget = self._plugin_loader.load_builtin_widget(
            plugin_id,
            context=self._plugin_context,
        )
        if not isinstance(widget, QWidget):
            raise TypeError(f"Plugin {plugin_id!r} did not create a QWidget")
        action_request = getattr(widget, "actionCenterRequested", None)
        if action_request is not None and hasattr(action_request, "connect"):
            action_request.connect(self._open_action_center_request)
        if plugin_id == "atlas_dashboard":
            self._schedule_post_render_services()
        return widget

    def _open_action_center_request(self, action_id: str, parameters=None) -> None:
        """Navigate and preselect only; workflow adapters never create a plan."""
        if self.switch_to_route("maintenance:action-center"):
            self._preselect_action_center(action_id, parameters)

    def _find_or_create_category(self, category: str) -> QTreeWidgetItem:
        """Find or create a category tree item, using cache for O(1) lookup."""
        if category in self._category_items:
            return self._category_items[category]

        category_item = QTreeWidgetItem(self.sidebar)
        category_item.setText(0, category)
        category_item.setData(0, _ROLE_DESC, category)
        category_item.setExpanded(True)
        self._set_tree_item_icon(category_item, CATEGORY_ICONS.get(category, ""))
        self._category_items[category] = category_item
        return category_item

    def _create_tab_item(
        self,
        category_item: QTreeWidgetItem,
        name: str,
        icon: str,
        badge: str = "",
        description: str = "",
        disabled: bool = False,
        disabled_reason: str = "",
    ) -> QTreeWidgetItem:
        """Create a sidebar tree item for a tab."""
        badge_suffix = ""
        if badge == "recommended":
            badge_suffix = "  ★"
        elif badge == "advanced":
            badge_suffix = "  ⚙"

        item = QTreeWidgetItem(category_item)
        item.setText(0, f"{name}{badge_suffix}")
        item.setData(0, _ROLE_NAME, name)
        self._set_tree_item_icon(item, icon)

        if disabled:
            item.setDisabled(True)
            tooltip = disabled_reason if disabled_reason else f"{name} is not available on this system."
            item.setToolTip(0, tooltip)
        else:
            item.setData(0, _ROLE_DESC, description)
            item.setData(0, _ROLE_BADGE, badge)
            if description:
                item.setToolTip(0, description)

        return item

    def _register_in_index(self, plugin_id: str, entry: "SidebarEntry", scroll_widget: "QWidget | None" = None) -> None:
        """Register a tab in the sidebar index and content area.

        Args:
            plugin_id: Canonical plugin identifier (key in _sidebar_index).
            entry: SidebarEntry holding the original (unwrapped) page widget.
            scroll_widget: Wrapped scroll-area widget to add to the content stack.
                           When None, entry.page_widget is added directly.
        """
        self._sidebar_index[plugin_id] = entry
        self._pages_cache = None  # invalidate backward-compat cache
        target = scroll_widget if scroll_widget is not None else entry.page_widget
        entry.content_widget = target
        self.content_area.addWidget(target)

    def _add_plugin_page(
        self,
        meta: PluginMetadata,
        widget: LazyWidget,
        compat: CompatStatus,
        *,
        visible_in_sidebar: bool = True,
    ) -> None:
        """Register a plugin page in the sidebar and content area."""
        item: QTreeWidgetItem | None = None
        if visible_in_sidebar:
            category_item = self._find_or_create_area(meta.id, meta.category)
            item = self._create_tab_item(
                category_item,
                meta.name,
                meta.icon,
                meta.badge,
                meta.description,
                disabled=not compat.compatible,
                disabled_reason=compat.reason,
            )
        if not compat.compatible:
            page_widget = self._wrap_page_widget(DisabledPluginPage(meta, compat.reason))
        else:
            page_widget = self._wrap_page_widget(widget)
        if item is not None:
            item.setData(0, Qt.ItemDataRole.UserRole, page_widget)
            item.setData(0, _ROLE_ROUTE_ID, meta.id)
        area = area_for_plugin(meta.id)
        entry = SidebarEntry(
            plugin_id=meta.id,
            display_name=meta.name,
            tree_item=item,
            page_widget=widget,
            metadata=meta,
            area_id=area.id if area else meta.category,
            visible_in_sidebar=visible_in_sidebar,
        )
        self._register_in_index(meta.id, entry, scroll_widget=page_widget)

    def _start_pulse_listener(self):
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

    def _initialize_background_services(self) -> None:
        """Start tray and Pulse only for an explicitly background-enabled app."""
        if not self._background_services_enabled():
            return
        self.setup_tray()
        self._start_pulse_listener()

    def _schedule_post_render_services(self) -> None:
        """Schedule nonessential shell work after meaningful Home exists."""
        if self._post_render_services_scheduled:
            return
        self._post_render_services_scheduled = True
        QTimer.singleShot(250, self._initialize_post_render_services)

    def _initialize_post_render_services(self) -> None:
        """Initialize deferred UI and probes outside the first-render hot path."""
        self._start_status_refresh()
        QTimer.singleShot(0, self.check_dependencies)

    def _start_status_refresh(self) -> None:
        """Start periodic sidebar status refresh after first render."""
        if self._status_timer is not None:
            return
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._refresh_status_indicators)
        self._status_timer.start(30000)
        try:
            from utils.settings import SettingsManager

            check_on_start = bool(
                SettingsManager.instance().get("check_updates_on_start", True)
            )
        except (ImportError, OSError, RuntimeError, TypeError, ValueError):
            check_on_start = True
        if check_on_start:
            QTimer.singleShot(5000, self._refresh_status_indicators)

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
                tab_name = item.text(0).replace("  ★", "").replace("  ⚙", "").strip()
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

    def add_page(
        self,
        name: str,
        icon: str,
        widget,
        category: str = "General",
        description: str = "",
        badge: str = "",
        disabled: bool = False,
        disabled_reason: str = "",
    ) -> None:
        category_item = self._find_or_create_category(category)
        item = self._create_tab_item(category_item, name, icon, badge, description, disabled, disabled_reason)

        if disabled:
            placeholder_meta = PluginMetadata(
                id=name.lower().replace(" ", "_"),
                name=name,
                description=description,
                category=category,
                icon=icon,
                badge=badge,
            )
            page_widget = self._wrap_page_widget(DisabledPluginPage(placeholder_meta, disabled_reason))
        else:
            page_widget = self._wrap_page_widget(widget)

        plugin_id = name.lower().replace(" ", "_")
        item.setData(0, Qt.ItemDataRole.UserRole, page_widget)
        item.setData(0, _ROLE_ROUTE_ID, plugin_id)
        meta = PluginMetadata(id=plugin_id, name=name, description=description, category=category, icon=icon, badge=badge)
        entry = SidebarEntry(
            plugin_id=plugin_id,
            display_name=name,
            tree_item=item,
            page_widget=widget,
            metadata=meta,
        )
        self._register_in_index(plugin_id, entry, scroll_widget=page_widget)

    def _wrap_page_widget(self, widget: QWidget) -> QScrollArea:
        """
        Wrap a page widget in a scroll area.

        Prevents dense tabs from being vertically compressed on smaller
        displays; users can scroll instead of seeing clipped/collapsed controls.
        """
        scroll = QScrollArea()
        scroll.setObjectName("pageScroll")
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        scroll.setWidget(widget)
        return scroll

    def change_page(self, current, previous):
        if not current:
            return

        widget = current.data(0, Qt.ItemDataRole.UserRole)
        if widget:
            self.content_area.setCurrentWidget(widget)
            route = resolve(str(current.data(0, _ROLE_ROUTE_ID) or current.data(0, _ROLE_NAME) or ""))
            self._active_route_id = route.id if route else ""
            if route:
                self._set_active_plugin(route.plugin_id)
            if route and route.subroute:
                self._activate_route_widget(route)
            self._update_breadcrumb(current)
        else:
            # Category item: expand and auto-select first child
            if current.childCount() > 0:
                current.setExpanded(True)
                self.sidebar.setCurrentItem(current.child(0))

    def _update_breadcrumb(self, item):
        """Update breadcrumb bar with current route category > page."""
        parent = item.parent()
        # Use raw category name (stored in _ROLE_DESC on category items) for clean breadcrumb
        category = ""
        if parent:
            category = parent.data(0, _ROLE_DESC) or parent.text(0)
        page_name = item.data(0, _ROLE_NAME)
        if not page_name:
            raw = item.text(0)
            page_name = raw.replace("  ★", "").replace("  ⚙", "")
        page_name = str(page_name)
        desc = item.data(0, _ROLE_DESC) or ""
        route = resolve(self._active_route_id or str(item.data(0, _ROLE_ROUTE_ID) or ""))
        if route:
            area = area_for_plugin(route.plugin_id)
            category = area.label if area else route.category
            page_name = route.label
            desc = route.description
        elif parent:
            parent_route = str(parent.data(0, _ROLE_ROUTE_ID) or "")
            area = area_for_plugin(str(item.data(0, _ROLE_ROUTE_ID) or ""))
            category = area.label if area else parent_route or category
        self._bc_category.setText(category)
        self._bc_page.setText(page_name)
        self._bc_desc.setText(desc)
        if hasattr(self._breadcrumb_frame, "set_content"):
            self._breadcrumb_frame.set_content(category, page_name, desc)
        # Store parent item ref for breadcrumb click (v38.0)
        self._bc_parent_item = parent

    def _update_header_for_route(self, route: NavigationRoute, entry: SidebarEntry | None = None) -> None:
        """Render the focused page header when a route has no visible sidebar row."""
        placement = placement_for_route(route.id)
        destination = (
            get_destination(placement.destination_id) if placement is not None else None
        )
        area = area_for_plugin(route.plugin_id)
        category = destination.label if destination else (area.label if area else route.category)
        self._bc_category.setText(category)
        self._bc_page.setText(route.label)
        self._bc_desc.setText(route.description)
        if hasattr(self._breadcrumb_frame, "set_content"):
            self._breadcrumb_frame.set_content(category, route.label, route.description)
        self._bc_parent_item = entry.tree_item.parent() if entry and entry.tree_item else None

    @staticmethod
    def _normalize_route_label(value: str) -> str:
        """Normalize route labels and tab titles for loose subroute matching."""
        cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in str(value))
        return " ".join(cleaned.split())

    def _real_widget_for_entry(self, entry: SidebarEntry) -> QWidget:
        """Return the realized page widget for a sidebar entry."""
        widget = entry.page_widget
        ensure_loaded = getattr(widget, "ensure_loaded", None)
        if callable(ensure_loaded):
            realized = ensure_loaded()
            if isinstance(realized, QWidget):
                return realized
        get_real_widget = getattr(widget, "get_real_widget", None)
        if callable(get_real_widget):
            realized = get_real_widget()
            if isinstance(realized, QWidget):
                return realized
        return widget

    def _set_active_plugin(self, plugin_id: str) -> None:
        """Run page lifecycle hooks once when the active top-level route changes."""
        plugin_id = str(plugin_id or "")
        if plugin_id == self._active_plugin_id:
            return

        registry = PluginRegistry.instance()
        get_plugin = getattr(registry, "get", lambda _plugin_id: None)
        previous = get_plugin(self._active_plugin_id) if self._active_plugin_id else None
        if previous is not None:
            try:
                previous.on_deactivate()
            except (AttributeError, RuntimeError, OSError, TypeError, ValueError) as exc:
                logger.debug("Plugin deactivation failed for %s: %s", self._active_plugin_id, exc)

        self._active_plugin_id = plugin_id
        if not plugin_id:
            return

        entry = self._sidebar_index.get(plugin_id)
        if entry is not None:
            self._real_widget_for_entry(entry)
        current = get_plugin(plugin_id)
        if current is not None:
            try:
                current.on_activate()
            except (AttributeError, RuntimeError, OSError, TypeError, ValueError) as exc:
                logger.debug("Plugin activation failed for %s: %s", plugin_id, exc)

    def _activate_route_widget(self, route: NavigationRoute) -> bool:
        """Activate a route's sub-navigation inside the realized plugin widget."""
        entry = self._sidebar_index.get(route.plugin_id)
        if not entry:
            return False
        widget = self._real_widget_for_entry(entry)

        activator = getattr(widget, "activate_route", None)
        if callable(activator):
            try:
                return bool(activator(route))
            except (RuntimeError, ValueError, TypeError) as exc:
                logger.debug("Route activator failed for %s: %s", route.id, exc)

        if not route.subroute:
            return True

        labels = {
            self._normalize_route_label(route.subroute),
            self._normalize_route_label(route.label),
        }
        labels.update(self._normalize_route_label(alias) for alias in route.aliases)

        for tab_widget in widget.findChildren(QTabWidget):
            for index in range(tab_widget.count()):
                tab_label = self._normalize_route_label(tab_widget.tabText(index))
                if tab_label in labels:
                    tab_widget.setCurrentIndex(index)
                    return True
        return False

    def _set_tree_item_icon(self, item: QTreeWidgetItem, icon_value: str) -> None:
        """Apply bundled icon-pack icon to a tree item when available."""
        if not icon_value:
            return
        item.setData(0, _ROLE_ICON, icon_value)
        self._apply_tree_item_icon(item)

    def _apply_tree_item_icon(self, item: QTreeWidgetItem) -> None:
        """Apply the correct icon tint for the item's current selection state."""
        icon_value = item.data(0, _ROLE_ICON)
        if not icon_value:
            return
        selected = self._is_sidebar_item_selected(item)
        tint = icon_tint_variant(str(icon_value), selected=selected)
        icon = get_qicon(str(icon_value), size=17, tint=tint)
        if hasattr(item, "setIcon"):
            try:
                item.setIcon(0, icon)
            except (TypeError, ValueError):
                logger.debug("Failed to apply tree icon", exc_info=True)

    def _copy_tree_item_icon(self, source: QTreeWidgetItem, target: QTreeWidgetItem) -> None:
        """Copy an existing icon from source to target item when supported."""
        icon_value = source.data(0, _ROLE_ICON)
        if icon_value:
            target.setData(0, _ROLE_ICON, icon_value)
            self._apply_tree_item_icon(target)
            return
        if not hasattr(source, "icon") or not hasattr(target, "setIcon"):
            return
        try:
            target.setIcon(0, source.icon(0))
        except (TypeError, ValueError):
            logger.debug("Failed to copy tree icon", exc_info=True)

    def _is_sidebar_item_selected(self, item: QTreeWidgetItem) -> bool:
        """Return True when item is current row or current row's parent category."""
        current = self.sidebar.currentItem() if hasattr(self, "sidebar") else None
        if current is None:
            return False
        if current is item:
            return True
        if item.parent() is None and current.parent() is item:
            return True
        return False

    def _refresh_sidebar_icon_tints(self) -> None:
        """Reapply icon variants after selection changes."""
        iterator = QTreeWidgetItemIterator(self.sidebar)
        while iterator.value():
            item = iterator.value()
            if item is None:
                break
            if item.data(0, _ROLE_ICON):
                self._apply_tree_item_icon(item)
            iterator += 1

    def _on_sidebar_selection_changed(self, current, previous) -> None:
        """Keep sidebar icon tint hierarchy in sync with the selected row."""
        self._refresh_sidebar_icon_tints()

    def _on_breadcrumb_category_click(self):
        """Navigate to the current destination's default route."""
        if getattr(self, "_shell_uses_destinations", False) is True:
            destination = get_destination(self._active_destination_id)
            if destination is not None:
                self.switch_to_route(destination.default_route_id)
            return
        parent = getattr(self, "_bc_parent_item", None)
        if parent and parent.childCount() > 0:
            parent.setExpanded(True)
            self.sidebar.setCurrentItem(parent.child(0))

    def set_status(self, text: str):
        """Set status bar message (can be called from any tab)."""
        self._status_label.setText(text)
        self._update_status_chrome()

    def show_undo_button(self, description: str = ""):
        """Show the undo button in the status bar after an undoable action."""
        if description:
            self._status_label.setText(self.tr("✓ ") + description)
        self._undo_btn.setVisible(True)
        self._update_status_chrome()

    def _on_undo_clicked(self):
        """Execute undo via HistoryManager and update status."""
        try:
            hm = HistoryManager()
            result = hm.undo_last_action()
            if result.success:
                self.show_status_toast(result.message)
            else:
                self.show_status_toast(result.message, error=True)
        except (RuntimeError, OSError, ValueError) as e:
            logger.debug("Undo failed: %s", e)
            self.show_status_toast(self.tr("Undo failed"), error=True)
        self._undo_btn.setVisible(False)
        self._update_status_chrome()

    def show_status_toast(self, message: str, error: bool = False, duration: int = 3000):
        """Show a temporary status-bar toast notification (v38.0)."""
        self._status_label.setText(message)
        if error:
            self._status_label.setProperty("toast", "error")
        else:
            self._status_label.setProperty("toast", "success")
        self._status_label.style().unpolish(self._status_label)
        self._status_label.style().polish(self._status_label)
        self._update_status_chrome()

        from PyQt6.QtCore import QTimer

        QTimer.singleShot(duration, self._clear_toast)

    def _clear_toast(self):
        """Clear toast styling from the status bar."""
        self._status_label.setText("")
        self._status_label.setProperty("toast", "")
        self._status_label.style().unpolish(self._status_label)
        self._status_label.style().polish(self._status_label)
        self._update_status_chrome()

    def _update_status_chrome(self) -> None:
        """Show activity chrome only while it carries actionable information."""
        has_message = bool(self._status_label.text().strip())
        has_undo = self._undo_btn.isVisible()
        self._status_frame.setVisible(has_message or has_undo)

    def switch_to_route(self, route_id: str, *, record_history: bool = True) -> bool:
        """Switch through policy to a canonical route ID or compatibility alias."""
        route = resolve(str(route_id))
        if not route:
            logger.debug("switch_to_route: no route for '%s'", route_id)
            return False

        if getattr(self, "_shell_uses_destinations", False) is True:
            result = NavigationPolicy.evaluate(route.id, self._navigation_context)
            if (
                result.direct_link_behavior is DirectLinkBehavior.REDIRECT
                and result.redirect_route_id
            ):
                return self.switch_to_route(
                    result.redirect_route_id,
                    record_history=record_history,
                )
            if result.decision is not NavigationDecision.VISIBLE:
                destination = get_destination(result.destination_id)
                if destination is not None:
                    self._selecting_destination = True
                    self.sidebar.select_destination(destination.id)
                    self._selecting_destination = False
                self.destination_host.show_policy_result(result)
                return False

        entry = self._sidebar_index.get(route.plugin_id)
        if not entry:
            logger.debug(
                "switch_to_route: route '%s' references unavailable plugin '%s'",
                route.id,
                route.plugin_id,
            )
            return False

        if entry.tree_item is not None:
            self.sidebar.setCurrentItem(entry.tree_item)
        elif entry.content_widget is not None:
            self.content_area.setCurrentWidget(entry.content_widget)
        if getattr(self, "_shell_uses_destinations", False) is True:
            self._sync_destination_shell(route.id)
        self._active_route_id = route.id
        self._set_active_plugin(route.plugin_id)
        activated = self._activate_route_widget(route)
        if entry.tree_item is not None:
            self._update_breadcrumb(entry.tree_item)
        else:
            self._update_header_for_route(route, entry)
        if not activated:
            logger.debug("switch_to_route: plugin selected but subroute did not activate: %s", route.id)
        if record_history:
            self._record_route_history(route.id)
        return True

    def _record_route_history(self, route_id: str) -> None:
        """Record successful route navigation without duplicate adjacent entries."""
        if not isinstance(getattr(self, "_route_history", None), list):
            self._route_history = []
        if not isinstance(getattr(self, "_route_history_index", None), int):
            self._route_history_index = -1
        if self._route_history_index >= 0:
            current = self._route_history[self._route_history_index]
            if current == route_id:
                return
        del self._route_history[self._route_history_index + 1 :]
        self._route_history.append(route_id)
        self._route_history_index = len(self._route_history) - 1

    def navigate_back(self) -> bool:
        """Navigate to the previous successful route."""
        if self._route_history_index <= 0:
            return False
        target_index = self._route_history_index - 1
        route_id = self._route_history[target_index]
        if not self.switch_to_route(route_id, record_history=False):
            return False
        self._route_history_index = target_index
        return True

    def navigate_forward(self) -> bool:
        """Navigate to the next successful route."""
        if self._route_history_index + 1 >= len(self._route_history):
            return False
        target_index = self._route_history_index + 1
        route_id = self._route_history[target_index]
        if not self.switch_to_route(route_id, record_history=False):
            return False
        self._route_history_index = target_index
        return True

    def switch_to_tab(self, name):
        """Switch to a route by ID/alias, then plugin ID or display name fallback."""
        route = resolve(str(name))
        if route and self.switch_to_route(route.id):
            return True

        entry = self._sidebar_index.get(name)
        if entry:
            if entry.tree_item is not None:
                self.sidebar.setCurrentItem(entry.tree_item)
                self._active_route_id = str(entry.tree_item.data(0, _ROLE_ROUTE_ID) or entry.plugin_id)
            elif entry.content_widget is not None:
                self.content_area.setCurrentWidget(entry.content_widget)
                self._active_route_id = entry.plugin_id
            self._set_active_plugin(entry.plugin_id)
            return True

        # Fallback: search by display name
        for entry in self._sidebar_index.values():
            if name in entry.display_name:
                logger.debug(
                    "switch_to_tab: matched by display name '%s', prefer plugin ID '%s'",
                    name,
                    entry.plugin_id,
                )
                if entry.tree_item is not None:
                    self.sidebar.setCurrentItem(entry.tree_item)
                    self._active_route_id = str(entry.tree_item.data(0, _ROLE_ROUTE_ID) or entry.plugin_id)
                else:
                    self._active_route_id = entry.plugin_id
                    if entry.content_widget is not None:
                        self.content_area.setCurrentWidget(entry.content_widget)
                self._set_active_plugin(entry.plugin_id)
                return True

        logger.debug("switch_to_tab: no match for '%s'", name)
        return False

    def _setup_command_palette_shortcut(self):
        """Compatibility name for registering both global-search shortcuts."""
        self._setup_global_search_shortcuts()

    def _setup_global_search_shortcuts(self) -> None:
        """Bind route/settings search and action search to the same dialog."""
        global_shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        global_shortcut.activated.connect(
            lambda: self._show_global_search(actions_only=False)
        )
        action_shortcut = QShortcut(QKeySequence("Ctrl+Shift+K"), self)
        action_shortcut.activated.connect(
            lambda: self._show_global_search(actions_only=True)
        )
        self._global_search_shortcuts = (global_shortcut, action_shortcut)

    def _show_command_palette(self):
        """Compatibility entry point for the shared global search."""
        self._show_global_search(actions_only=False)

    def _setup_quick_actions(self):
        """Compatibility no-op; action discovery uses global search shortcuts."""

    def _show_quick_actions(self):
        """Compatibility entry point for action-filtered global search."""
        self._show_global_search(actions_only=True)

    def _show_global_search(self, *, actions_only: bool = False) -> None:
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
                search_filter=(
                    SearchFilter.ACTIONS if actions_only else SearchFilter.ALL
                ),
                parent=self,
            )
            dialog.exec()
        except ImportError:
            logger.debug("Global search module not available", exc_info=True)

    def _activate_global_search_result(self, result) -> bool:
        """Navigate to a result and optionally preselect an Action Center item."""
        route_id = str(getattr(result, "route_id", "") or "")
        if not route_id or not self.switch_to_route(route_id):
            return False
        action_id = str(getattr(result, "action_id", "") or "")
        if action_id:
            self._preselect_action_center(action_id)
        return True

    def _preselect_action_center(self, action_id: str, parameters=None) -> bool:
        """Select an Action Center candidate without planning or running it."""
        entry = self._sidebar_index.get("maintenance")
        if entry is None:
            return False
        widget = self._real_widget_for_entry(entry)
        preselect = getattr(widget, "preselect_action", None)
        if not callable(preselect):
            return False
        if parameters is None:
            return bool(preselect(action_id))
        return bool(preselect(action_id, parameters))

    def _toggle_sidebar(self):
        """Toggle sidebar between expanded and collapsed states."""
        self._auto_sidebar_collapsed = False
        self._set_sidebar_collapsed(not self._sidebar_collapsed)

    def _set_sidebar_collapsed(self, collapsed: bool) -> None:
        """Apply sidebar collapsed/expanded state without changing route data."""
        if not collapsed:
            self._sidebar_container.setFixedWidth(self._sidebar_expanded_width)
            self.sidebar.setVisible(True)
            self._set_sidebar_icon_only(False)
            self._sidebar_toggle.setText("◀")
            self._sidebar_toggle.setToolTip(self.tr("Collapse sidebar"))
            self._sidebar_collapsed = False
        else:
            collapsed_width = getattr(getattr(self, "_metrics", None), "sidebar_collapsed_width", int(self._line_height * 4))
            self._sidebar_container.setFixedWidth(collapsed_width)
            self.sidebar.setVisible(True)
            self._set_sidebar_icon_only(True)
            self._sidebar_toggle.setText("▶")
            self._sidebar_toggle.setToolTip(self.tr("Expand sidebar"))
            self._sidebar_collapsed = True

    def resizeEvent(self, event) -> None:
        """Apply responsive sidebar breakpoints as the window changes size."""
        try:
            width = int(self.width())
            if width < 900 and not self._sidebar_collapsed:
                self._auto_sidebar_collapsed = True
                self._set_sidebar_collapsed(True)
            elif width > 1120 and self._auto_sidebar_collapsed:
                self._auto_sidebar_collapsed = False
                self._set_sidebar_collapsed(False)
        except (TypeError, ValueError, AttributeError, RuntimeError):
            logger.debug("Responsive sidebar resize update failed", exc_info=True)
        super().resizeEvent(event)

    def _sidebar_display_text(self, item: QTreeWidgetItem) -> str:
        """Return the expanded display text for a sidebar item."""
        name = item.data(0, _ROLE_NAME)
        if name:
            badge = item.data(0, _ROLE_BADGE) or ""
            suffix = ""
            if badge == "recommended":
                suffix = "  ★"
            elif badge == "advanced":
                suffix = "  ⚙"
            return f"{name}{suffix}"
        return str(item.data(0, _ROLE_DESC) or item.text(0))

    def _set_sidebar_icon_only(self, collapsed: bool) -> None:
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

    def _setup_keyboard_shortcuts(self):
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

    def _select_category(self, index: int):
        """Compatibility name for selecting a flat destination by position."""
        if index < self.sidebar.topLevelItemCount():
            item = self.sidebar.topLevelItem(index)
            self.sidebar.setCurrentItem(item)

    def _select_next_item(self):
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

    def _select_prev_item(self):
        current = self.sidebar.currentItem()
        if not current:
            return

        # Try to find item above
        prev_item = self.sidebar.itemAbove(current)
        if prev_item:
            self.sidebar.setCurrentItem(prev_item)
        else:
            # Wrap around to the last destination.
            self.sidebar.setCurrentItem(
                self.sidebar.topLevelItem(self.sidebar.topLevelItemCount() - 1)
            )

    def _show_shortcut_help(self):
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

    def show_toast(self, title: str, message: str, category: str = "general"):
        """Show an animated toast notification at the top-right."""
        try:
            from ui.notification_toast import NotificationToast

            if self._toast_widget is None:
                self._toast_widget = NotificationToast(self)
            self._toast_widget.show_toast(title, message, category)
        except (RuntimeError, ImportError) as e:
            logger.debug("Failed to show toast notification: %s", e)

    def _refresh_status_indicators(self):
        """Update sidebar status indicators from live system data (v29.0)."""
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

    def _set_tab_status(self, tab_id: str, status: str, tooltip: str = ""):
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

    def apply_navigation_mode(self, mode=None):
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

    def _check_first_run(self):
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

    def setup_tray(self):
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

    def _toggle_focus_mode(self):
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

    def quit_app(self):
        self._set_active_plugin("")
        # Stop Pulse listener
        if self.pulse_thread:
            self.pulse_thread.stop()

        if self.tray_icon:
            self.tray_icon.hide()
        from PyQt6.QtWidgets import QApplication

        QApplication.quit()

    def closeEvent(self, event):
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
            # Clean up page resources (timers, schedulers)
            self._set_active_plugin("")
            registry = PluginRegistry.instance()
            list_all = getattr(registry, "list_all", lambda: [])
            plugins = list(list_all())
            if not plugins:
                plugins = [entry.page_widget for entry in self._sidebar_index.values()]
            for plugin in plugins:
                if hasattr(plugin, "cleanup"):
                    try:
                        plugin.cleanup()
                    except (RuntimeError, OSError) as e:
                        logger.debug("Failed to cleanup page on close: %s", e)
            event.accept()

    def check_dependencies(self):
        from services.system.system import cached_which

        critical = ["dnf", "pkexec"]
        missing = [tool for tool in critical if not cached_which(tool)]
        if missing:
            self.show_doctor()

    def show_doctor(self):
        from ui.doctor import DependencyDoctor

        doctor = DependencyDoctor(self)
        doctor.exec()

    # ==================== v13.5 Theme Management ====================

    def load_theme(self, name: str = "dark") -> None:
        """
        Load and apply a QSS theme by name.

        Supported names: ``"dark"`` (modern.qss), ``"light"`` (light.qss),
        and ``"highcontrast"`` (highcontrast.qss).
        Falls back silently to no stylesheet if the file is missing.
        """
        theme_map = {
            "dark": "modern.qss",
            "light": "light.qss",
            "highcontrast": "highcontrast.qss",
        }
        filename = theme_map.get(name, "modern.qss")
        assets_dir = os.path.join(os.path.dirname(__file__), "..", "assets")
        qss_path = os.path.join(assets_dir, filename)

        try:
            with open(qss_path, "r") as fh:
                stylesheet = fh.read()
            from PyQt6.QtWidgets import QApplication

            app = QApplication.instance()
            if isinstance(app, QApplication):
                app.setStyleSheet(stylesheet)
        except OSError:
            logger.debug("Failed to load theme stylesheet", exc_info=True)

    @staticmethod
    def detect_system_theme() -> str:
        """
        Detect the system colour-scheme preference via
        ``gsettings`` (GNOME / GTK) and return ``"dark"`` or ``"light"``.

        Returns ``"dark"`` when detection fails.
        """
        from services.desktop import DesktopUtils

        return DesktopUtils.detect_color_scheme()
