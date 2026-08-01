"""Route-aware application shell with lazy destination navigation."""

import logging
from dataclasses import dataclass, field
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
    resolve,
)
from core.plugins import PluginInterface, PluginRegistry
from core.plugins.metadata import CompatStatus, PluginMetadata
from core.plugins.registry import CATEGORY_ICONS
from PyQt6.QtCore import QRect, Qt, QTimer
from PyQt6.QtGui import QPainter
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
from utils.history import HistoryManager
from utils.log import get_logger
from ui.icon_pack import get_qicon, icon_tint_variant
from ui.design import semantic_qcolor
from ui.layout_primitives import LayoutMetrics, PageHeader
from ui.lazy_widget import LazyWidget
from ui.navigation import DestinationHost, DestinationSidebar
from ui.main_window_interactions import MainWindowInteractionMixin
from ui.main_window_services import MainWindowServiceMixin
from ui.main_window_shell import MainWindowShellMixin

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

    _STATUS_ROLES = {
        "ok": "success",
        "warning": "warning",
        "error": "error",
    }

    def paint(self, painter: "QPainter | None", option: QStyleOptionViewItem, index) -> None:
        """Paint the item, adding a colored status dot on the right when status is set."""
        super().paint(painter, option, index)

        if painter is None:
            return

        status = index.data(_ROLE_STATUS)
        if not status or status not in self._STATUS_ROLES:
            return

        color = semantic_qcolor(self._STATUS_ROLES[status])
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


class MainWindow(
    MainWindowServiceMixin,
    MainWindowInteractionMixin,
    MainWindowShellMixin,
    QMainWindow,
):
    def __init__(self, runtime=None):
        super().__init__()
        self._runtime = runtime
        self._runtime_cleaned = False

        # Initialize logger for this class
        self.logger = logging.getLogger(__name__)

        # Keep native title-bar decorations enabled.
        # This avoids KDE/Wayland/X11 edge-cases where client content can
        # appear to bleed into the top chrome when frameless/custom hints are used.
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, False)
        self.setWindowFlag(Qt.WindowType.CustomizeWindowHint, False)
        self.setWindowTitle(self.tr("Loofi Fedora Tweaks"))
        self.setAccessibleName(self.tr("Loofi Fedora Tweaks"))
        self.setAccessibleDescription(self.tr("Fedora system settings and maintenance control center"))

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
        self._sidebar_layout = sidebar_layout

        sidebar_chrome = QHBoxLayout()
        sidebar_chrome.setContentsMargins(0, 0, 0, 0)
        sidebar_chrome.setSpacing(6)

        # Compact semantic sidebar control.
        sidebar_chrome.addStretch()
        self._sidebar_toggle = QToolButton()
        self._sidebar_toggle.setObjectName("sidebarToggle")
        self._sidebar_toggle.setFixedHeight(36)
        self._sidebar_toggle.clicked.connect(self._toggle_sidebar)
        sidebar_chrome.addWidget(self._sidebar_toggle)
        sidebar_layout.addLayout(sidebar_chrome)

        self._global_search_button = QPushButton(self.tr("Search  Ctrl+K"))
        self._global_search_button.setObjectName("globalSearchAffordance")
        self._global_search_button.setIcon(get_qicon("search", size=18))
        self._global_search_button.setAccessibleName(self.tr("Search routes, settings, and actions"))
        self._global_search_button.setToolTip(self.tr("Search routes, settings, and actions (Ctrl+K)"))
        self._global_search_button.clicked.connect(lambda: self._show_global_search(actions_only=False))
        sidebar_layout.addWidget(self._global_search_button)

        # Track sidebar expanded width and state
        self._sidebar_container = sidebar_container
        self._sidebar_expanded_width = sidebar_width
        self._sidebar_collapsed = False
        self._auto_sidebar_collapsed = False
        self._set_sidebar_toggle_state(False)

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

        shell_body = QWidget()
        shell_body.setObjectName("shellBody")
        self._shell_body_layout = QGridLayout(shell_body)
        self._shell_body_layout.setContentsMargins(0, 0, 0, 0)
        self._shell_body_layout.setSpacing(0)

        self.destination_host = DestinationHost()
        self.destination_host.routeRequested.connect(self.switch_to_route)

        # Content Area
        self.content_area = QStackedWidget()
        self._shell_body_layout.addWidget(self.destination_host, 0, 0)
        self._shell_body_layout.addWidget(self.content_area, 0, 1)
        self._shell_body_layout.setColumnStretch(1, 1)
        self._section_navigation_compact = False
        right_side.addWidget(shell_body, 1)

        # Status bar
        self._status_frame = QFrame()
        self._status_frame.setObjectName("statusBar")
        self._status_frame.setMinimumHeight(self._metrics.status_height)
        sb_layout = QHBoxLayout(self._status_frame)
        sb_layout.setContentsMargins(12, 0, 12, 0)
        self._status_label = QLabel("")
        self._status_label.setObjectName("statusText")
        self._status_label.setAccessibleName(self.tr("Activity status"))
        sb_layout.addWidget(self._status_label)

        # Undo control for the latest reversible application action.
        self._undo_btn = QPushButton(self.tr("Undo"))
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
        self._page_header_action_owner: QWidget | None = None
        self._active_plugin_id = ""
        self._active_destination_id = ""
        self._selecting_destination = False
        self._shell_uses_destinations = True
        self._route_history: list[str] = []
        self._route_history_index = -1

        # Build the sidebar from inert plugin specifications.
        context = {
            "main_window": self,
            "config_manager": ConfigManager,  # class, not instance
            "executor": None,  # populated after executor init
        }
        self._build_sidebar_from_registry(context)
        try:
            initial_shell_width = int(self.width())
        except (TypeError, ValueError, AttributeError):
            initial_shell_width = 1180
        self._apply_responsive_shell(initial_shell_width)

        # Select Home after all lazy route entries are registered.
        if self.sidebar.topLevelItemCount() > 0:
            self.sidebar.setCurrentItem(self.sidebar.topLevelItem(0))

        # Background-only services are conditional on persisted settings.
        self._initialize_background_services()

        # Ctrl+K and Ctrl+Shift+K share one policy-backed discovery surface.
        self._setup_command_palette_shortcut()

        # Register application keyboard shortcuts after navigation exists.
        self._setup_keyboard_shortcuts()

        # First-run wizard
        self._check_first_run()
        if self._runtime is not None:
            from core.application_runtime import ShutdownResource

            self._runtime.register(
                "main-window",
                ShutdownResource(
                    request_stop=self._request_runtime_stop,
                    wait_for_stop=self._wait_for_runtime_stop,
                ),
            )

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
        from core.plugins.components import discover_builtin_components
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
            installed_components=discover_builtin_components(specs),
            fedora_variant=(FedoraVariant.ATOMIC if is_atomic else FedoraVariant.TRADITIONAL),
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
        finding_request = getattr(widget, "findingActionReviewRequested", None)
        if finding_request is not None and hasattr(finding_request, "connect"):
            finding_request.connect(self._open_system_check_action_request)
        check_request = getattr(widget, "systemCheckRequested", None)
        if check_request is not None and hasattr(check_request, "connect"):
            check_request.connect(self._start_follow_up_system_check)
        route_request = getattr(widget, "routeRequested", None)
        if route_request is not None and hasattr(route_request, "connect"):
            route_request.connect(self._open_route_request)
        if plugin_id == "atlas_dashboard":
            self._schedule_post_render_services()
        return widget

    def _open_route_request(self, route_id: str, _preselection=None) -> None:
        """Navigate through the canonical manifest; metadata remains inert."""
        self.switch_to_route(route_id)

    def _open_action_center_request(self, action_id: str, parameters=None) -> None:
        """Navigate and preselect only; workflow adapters never create a plan."""
        if self.switch_to_route("maintenance:action-center"):
            self._preselect_action_center(action_id, parameters)

    def _open_system_check_action_request(self, action_id: str, context=None) -> None:
        """Carry identifiers only; Action Center re-resolves persisted evidence."""
        if self.switch_to_route("maintenance:action-center"):
            self._preselect_action_center(
                action_id,
                finding_context=dict(context or {}),
            )

    def _start_follow_up_system_check(self, _context=None) -> None:
        """Start collection only after the user's explicit Check again action."""
        if not self.switch_to_route("atlas_dashboard"):
            return
        entry = self._sidebar_index.get("atlas_dashboard")
        if entry is None:
            return
        widget = self._real_widget_for_entry(entry)
        start = getattr(widget, "start_system_check", None)
        if callable(start):
            start()

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
        badge_suffix = _BADGE_SUFFIXES.get(badge, "")

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
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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
            self._sync_page_header_actions(route)
            self._update_breadcrumb(current)
        else:
            # Category item: expand and auto-select first child
            if current.childCount() > 0:
                current.setExpanded(True)
                self.sidebar.setCurrentItem(current.child(0))

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
        self._status_label.setAccessibleDescription(text)
        self._update_status_chrome()

    def show_undo_button(self, description: str = ""):
        """Show the undo button in the status bar after an undoable action."""
        if description:
            self._status_label.setText(description)
            self._status_label.setAccessibleDescription(description)
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
        """Show a temporary status-bar notification."""
        self._status_label.setText(message)
        self._status_label.setAccessibleDescription(message)
        if error:
            self._status_label.setProperty("toast", "error")
        else:
            self._status_label.setProperty("toast", "success")
        self._status_label.style().unpolish(self._status_label)
        self._status_label.style().polish(self._status_label)
        self._update_status_chrome()

        QTimer.singleShot(duration, self._clear_toast)

    def _clear_toast(self):
        """Clear toast styling from the status bar."""
        self._status_label.setText("")
        self._status_label.setAccessibleDescription("")
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
            if result.direct_link_behavior is DirectLinkBehavior.REDIRECT and result.redirect_route_id:
                return self.switch_to_route(
                    result.redirect_route_id,
                    record_history=record_history,
                )
            if result.decision is not NavigationDecision.VISIBLE:
                self._sync_page_header_actions(None)
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
        self._sync_page_header_actions(route)
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
