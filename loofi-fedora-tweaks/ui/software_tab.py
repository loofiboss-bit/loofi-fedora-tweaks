"""
Software Tab - Consolidated tab merging Applications and Repositories.
Part of v11.0 "Aurora Update".

Uses a route-owned stack so the application shell remains the only owner of
section navigation.
"""

import typing

import logging

from core.plugins.metadata import PluginMetadata
from core.product_catalog import plugin_metadata_for_module
from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QComboBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from utils.command_runner import CommandRunner
from utils.software_utils import SoftwareUtils

from ui.base_tab import BaseTab
from ui.components import DetailsDisclosure, PageScaffold, StatusBadge
from ui.shared_states import EmptyState, LoadingState, UnavailableState
from ui.tooltips import (
    SW_CODECS,
    SW_FLATHUB,
    SW_RPM_FUSION,
    SW_SEARCH,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sub-tab: Applications
# ---------------------------------------------------------------------------


class _ApplicationsSubTab(BaseTab):
    """Sub-tab containing all application management functionality.

    Preserves every feature from the original AppsTab:
    - Remote/cached app config loading via AppConfigFetcher
    - Scrollable app list with install status check
    - Per-app install buttons (green = installed, clickable = available)
    - Refresh Status button
    - Output log with command feedback
    """

    actionCenterRequested = pyqtSignal(str, object)

    def __init__(self: typing.Any) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scaffold = PageScaffold(
            self.tr("Applications"),
            self.tr("Search the application catalogue and review install state before changing packages."),
        )
        root.addWidget(self.scaffold)
        layout = self.scaffold.content_layout

        # Header with Refresh Button
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel(self.tr("Essential Applications")))
        header_layout.addStretch()
        btn_refresh = QPushButton(self.tr("Refresh Status"))
        btn_refresh.setAccessibleName(self.tr("Refresh app status"))
        btn_refresh.clicked.connect(self.refresh_list)
        header_layout.addWidget(btn_refresh)
        layout.addLayout(header_layout)

        # v42.0: Search/filter bar
        self._search_bar = QLineEdit()
        self._search_bar.setPlaceholderText(self.tr("Search applications..."))
        self._search_bar.setAccessibleName(self.tr("Search applications"))
        self._search_bar.setToolTip(SW_SEARCH)
        self._search_bar.setClearButtonEnabled(True)
        self._search_bar.textChanged.connect(self._filter_apps)
        filters = QHBoxLayout()
        filters.addWidget(self._search_bar, 1)
        self._source_filter = QComboBox()
        self._source_filter.setObjectName("applicationSourceFilter")
        self._source_filter.setAccessibleName(self.tr("Filter by application source"))
        for label, value in (
            (self.tr("All sources"), "all"),
            (self.tr("Fedora RPM"), "fedora"),
            (self.tr("Flathub"), "flatpak"),
            (self.tr("Other sources"), "other"),
        ):
            self._source_filter.addItem(label, value)
        self._source_filter.currentIndexChanged.connect(
            lambda _index: self._filter_apps(self._search_bar.text())
        )
        filters.addWidget(self._source_filter)
        self._status_filter = QComboBox()
        self._status_filter.setObjectName("applicationStatusFilter")
        self._status_filter.setAccessibleName(self.tr("Filter by installation status"))
        for label, value in (
            (self.tr("All statuses"), "all"),
            (self.tr("Installed"), "installed"),
            (self.tr("Available"), "available"),
            (self.tr("Source setup required"), "unavailable"),
        ):
            self._status_filter.addItem(label, value)
        self._status_filter.currentIndexChanged.connect(
            lambda _index: self._filter_apps(self._search_bar.text())
        )
        filters.addWidget(self._status_filter)
        layout.addLayout(filters)

        self.catalog_loading = LoadingState(self.tr("Loading the application catalogue…"))
        self.catalog_empty = EmptyState(
            self.tr("No applications to show"),
            self.tr("The catalogue will load when this page is opened."),
        )
        self.catalog_unavailable = UnavailableState(
            self.tr("Application catalogue unavailable"),
            self.tr("Use Refresh Status to try the cached or remote catalogue again."),
        )
        self.catalog_loading.hide()
        self.catalog_unavailable.hide()
        layout.addWidget(self.catalog_loading)
        layout.addWidget(self.catalog_empty)
        layout.addWidget(self.catalog_unavailable)

        # Scroll Area for apps list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout()
        self.scroll_content.setLayout(self.scroll_layout)
        scroll.setWidget(self.scroll_content)

        layout.addWidget(scroll)

        # Output Area (Shared)
        self.output_area = QTextEdit()
        self.output_area.setReadOnly(True)
        self.output_area.setMaximumHeight(200)

        # Loading starts on explicit route activation, never in the constructor.
        self.apps: list = []
        self.fetcher = None
        self._catalog_load_started = False
        self.refresh_list()

        self.output_details = DetailsDisclosure(summary=self.tr("Show application command output"))
        self.output_details.add_widget(self.output_area)
        layout.addWidget(self.output_details)

    def load_apps(self: typing.Any) -> typing.Any:
        """Start asynchronous loading of the app catalogue."""
        from utils.remote_config import AppConfigFetcher

        self.fetcher = AppConfigFetcher()
        self.fetcher.config_ready.connect(self.on_apps_loaded)
        self.fetcher.config_error.connect(self.on_apps_error)
        self.fetcher.start()
        return []  # Populated asynchronously

    def on_activate(self: typing.Any) -> None:
        if self._catalog_load_started:
            return
        self._catalog_load_started = True
        self.catalog_empty.hide()
        self.catalog_unavailable.hide()
        self.catalog_loading.show()
        self.apps = self.load_apps()

    def on_apps_loaded(self: typing.Any, apps: typing.Any) -> typing.Any:
        self.apps = apps
        self.catalog_loading.hide()
        self.catalog_unavailable.hide()
        self.catalog_empty.setVisible(not bool(apps))
        if not apps:
            self.catalog_empty.set_message(self.tr("No applications matched the available catalogue."))
        self.refresh_list()
        self.append_output(self.tr("Apps list updated from remote/cache.\n"))

    def on_apps_error(self: typing.Any, error: typing.Any) -> typing.Any:
        self.catalog_loading.hide()
        self.catalog_empty.hide()
        self.catalog_unavailable.set_message(self.tr("Catalogue loading failed: %s") % error)
        self.catalog_unavailable.show()
        self.append_output(self.tr("Error loading apps: {}\n").format(error))

    def refresh_list(self: typing.Any) -> typing.Any:
        """Clear and rebuild the apps list."""
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        for app in self.apps:
            self.add_app_row(self.scroll_layout, app)
        self.scroll_layout.addStretch()

    def add_app_row(self: typing.Any, layout: typing.Any, app_data: typing.Any) -> typing.Any:
        """Add one source-aware app row with a single install/remove action."""
        from services.software import ApplicationOperationService

        row_widget = QFrame()
        row_widget.setFrameShape(QFrame.Shape.StyledPanel)
        row_layout = QHBoxLayout()
        row_widget.setLayout(row_layout)

        # Defensive access for potentially missing keys
        app_name = app_data.get("name", "Unknown App")
        app_desc = app_data.get("desc", app_data.get("description", ""))
        presentation = ApplicationOperationService.describe(app_data)

        lbl_name = QLabel(f"<b>{app_name}</b>")
        lbl_desc = QLabel(app_desc)

        # Check if installed
        chk_cmd = app_data.get("check_cmd")
        is_installed = False
        if chk_cmd:
            is_installed = self.check_installed(chk_cmd)

        source_kind = (
            "flatpak"
            if presentation.source == "Flathub (Flatpak)"
            else "fedora"
            if presentation.source == "Fedora RPM"
            else "other"
        )
        status_kind = (
            "installed"
            if is_installed
            else "available"
            if presentation.available
            else "unavailable"
        )
        row_widget.setProperty(
            "appSearchText",
            " ".join((str(app_name), str(app_desc), presentation.source)).lower(),
        )
        row_widget.setProperty("appSource", source_kind)
        row_widget.setProperty("appStatus", status_kind)

        badges = QVBoxLayout()
        source_badge = StatusBadge(
            self.tr("Source: %1").replace("%1", presentation.source),
            kind="info",
        )
        source_badge.setObjectName("applicationSourceBadge")
        source_badge.setToolTip(presentation.explanation)
        status_badge = StatusBadge(
            self.tr("Installed")
            if is_installed
            else self.tr("Available")
            if presentation.available
            else self.tr("Source setup required"),
            kind="success" if is_installed else "neutral",
        )
        status_badge.setObjectName("applicationStatusBadge")
        badges.addWidget(source_badge)
        badges.addWidget(status_badge)

        btn_install = QPushButton(self.tr("Review install"))
        btn_install.setAccessibleName(self.tr("Review install for {}").format(app_name))

        if is_installed:
            btn_install.setText(self.tr("Review removal"))
            btn_install.setAccessibleName(self.tr("Review removal for {}").format(app_name))
            btn_install.setObjectName("swInstalledBtn")
            btn_install.clicked.connect(
                lambda checked, app=app_data: self.run_app_action(
                    app,
                    installed=True,
                )
            )
        elif not presentation.available:
            btn_install.setText(self.tr("Source setup required"))
            btn_install.setToolTip(presentation.explanation)
            btn_install.setEnabled(False)
        else:
            btn_install.clicked.connect(
                lambda checked, app=app_data: self.run_app_action(
                    app,
                    installed=False,
                )
            )

        row_layout.addWidget(lbl_name)
        row_layout.addWidget(lbl_desc)
        row_layout.addLayout(badges)
        row_layout.addStretch()
        row_layout.addWidget(btn_install)

        layout.addWidget(row_widget)

    def check_installed(self: typing.Any, cmd: typing.Any) -> typing.Any:
        """Run a check command silently to determine installation status."""
        return SoftwareUtils.is_check_command_satisfied(cmd)

    def install_app(self: typing.Any, app_data: typing.Any) -> typing.Any:
        """Compatibility adapter for callers that still request installation."""
        self.run_app_action(app_data, installed=False)

    def run_app_action(self: typing.Any, app_data: typing.Any, *, installed: bool) -> None:
        """Hand one normalized install/remove operation to Action Center."""
        from services.software import ApplicationOperationService

        presentation = ApplicationOperationService.describe(app_data)
        if not presentation.available or presentation.source not in {"Fedora RPM", "Flathub (Flatpak)"}:
            self.show_error(presentation.explanation)
            return
        source = "flatpak" if presentation.source == "Flathub (Flatpak)" else "fedora"
        action_id = "remove-application" if installed else "install-application"
        self.actionCenterRequested.emit(
            action_id,
            {"source": source, "package_id": presentation.package_id},
        )

    def append_output(self: typing.Any, text: typing.Any) -> typing.Any:
        self.output_area.moveCursor(self.output_area.textCursor().MoveOperation.End)
        self.output_area.insertPlainText(text)
        self.output_area.moveCursor(self.output_area.textCursor().MoveOperation.End)

    def command_finished(self: typing.Any, exit_code: typing.Any) -> typing.Any:
        self.append_output(self.tr("\nCommand finished with exit code: {}").format(exit_code))
        # Refresh list to update status if installation succeeded
        if exit_code == 0:
            self.show_success(self.tr("Operation completed successfully"))
            self.refresh_list()
        else:
            self.show_error(self.tr("Operation failed (exit code {})").format(exit_code))

    def _filter_apps(self: typing.Any, text: str) -> typing.Any:
        """Apply search, source, and installed-state filters together."""
        query = text.strip().lower()
        source = str(self._source_filter.currentData() or "all")
        status = str(self._status_filter.currentData() or "all")
        for i in range(self.scroll_layout.count()):
            item = self.scroll_layout.itemAt(i)
            widget = item.widget() if item else None
            if widget is None:
                continue
            if not isinstance(widget, QFrame):
                continue
            search_text = str(widget.property("appSearchText") or "")
            source_value = str(widget.property("appSource") or "")
            status_value = str(widget.property("appStatus") or "")
            matches_query = not query or query in search_text
            matches_source = source == "all" or source == source_value
            matches_status = status == "all" or status == status_value
            widget.setVisible(matches_query and matches_source and matches_status)


# ---------------------------------------------------------------------------
# Sub-tab: Repositories
# ---------------------------------------------------------------------------


class _RepositoriesSubTab(BaseTab):
    actionCenterRequested = pyqtSignal(str, object)
    """Sub-tab containing all repository management functionality.

    Preserves every feature from the original ReposTab:
    - RPM Fusion enable (Free & Non-Free)
    - Multimedia Codecs install
    - Flathub remote enable
    - COPR repository enable (Loofi Fedora Tweaks)
    - Output log
    """

    def __init__(self: typing.Any) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scaffold = PageScaffold(
            self.tr("Repositories"),
            self.tr("Review software sources before enabling repositories or installing codecs."),
        )
        root.addWidget(self.scaffold)
        layout = self.scaffold.content_layout

        # RPM Fusion Group
        fusion_group = QGroupBox(self.tr("RPM Fusion (Essential for media codecs & drivers)"))
        fusion_layout = QVBoxLayout()
        fusion_group.setLayout(fusion_layout)

        self.btn_enable_fusion = QPushButton(self.tr("Enable RPM Fusion (Free & Non-Free)"))
        self.btn_enable_fusion.setAccessibleName(self.tr("Enable RPM Fusion"))
        self.btn_enable_fusion.setToolTip(SW_RPM_FUSION)
        self.btn_enable_fusion.clicked.connect(self.enable_rpm_fusion)
        fusion_layout.addWidget(self.btn_enable_fusion)

        self.btn_install_codecs = QPushButton(self.tr("Install Multimedia Codecs (ffmpeg, gstreamer, etc.)"))
        self.btn_install_codecs.setAccessibleName(self.tr("Install codecs"))
        self.btn_install_codecs.setToolTip(SW_CODECS)
        self.btn_install_codecs.clicked.connect(self.install_multimedia_codecs)
        fusion_layout.addWidget(self.btn_install_codecs)

        layout.addWidget(fusion_group)

        # Flatpak Flathub
        flathub_group = QGroupBox(self.tr("Flathub (Flatpak)"))
        flathub_layout = QVBoxLayout()
        flathub_group.setLayout(flathub_layout)

        self.btn_enable_flathub = QPushButton(self.tr("Enable Flathub Remote"))
        self.btn_enable_flathub.setAccessibleName(self.tr("Enable Flathub"))
        self.btn_enable_flathub.setToolTip(SW_FLATHUB)
        self.btn_enable_flathub.clicked.connect(self.enable_flathub)
        flathub_layout.addWidget(self.btn_enable_flathub)

        layout.addWidget(flathub_group)

        # COPR Repos Section
        copr_group = QGroupBox(self.tr("COPR Repositories"))
        copr_layout = QVBoxLayout()
        copr_group.setLayout(copr_layout)

        copr_layout.addWidget(QLabel(self.tr("Common COPR Repositories:")))

        self.btn_copr_loofi = QPushButton(self.tr("Enable Loofi Fedora Tweaks COPR"))
        self.btn_copr_loofi.setAccessibleName(self.tr("Enable Loofi COPR"))
        self.btn_copr_loofi.clicked.connect(
            lambda: self.actionCenterRequested.emit("enable-loofi-copr", {})
        )
        copr_layout.addWidget(self.btn_copr_loofi)

        layout.addWidget(copr_group)

        # Output Area
        self.output_area = QTextEdit()
        self.output_area.setReadOnly(True)
        self.output_area.setMaximumHeight(200)
        self.output_details = DetailsDisclosure(summary=self.tr("Show repository command output"))
        self.output_details.add_widget(self.output_area)
        layout.addWidget(self.output_details)

    # -- Repository actions ------------------------------------------------

    def enable_rpm_fusion(self: typing.Any) -> typing.Any:
        self.actionCenterRequested.emit("enable-rpm-fusion", {})

    def install_multimedia_codecs(self: typing.Any) -> typing.Any:
        self.actionCenterRequested.emit("install-multimedia-codecs", {})

    def enable_flathub(self: typing.Any) -> typing.Any:
        self.actionCenterRequested.emit("enable-flathub", {})

    # -- Helpers -----------------------------------------------------------

    def append_output(self: typing.Any, text: typing.Any) -> typing.Any:
        self.output_area.moveCursor(self.output_area.textCursor().MoveOperation.End)
        self.output_area.insertPlainText(text)
        self.output_area.moveCursor(self.output_area.textCursor().MoveOperation.End)

    def command_finished(self: typing.Any, exit_code: typing.Any) -> typing.Any:
        self.append_output(self.tr("\nCommand finished with exit code: {}").format(exit_code))
        if exit_code == 0:
            self.show_success(self.tr("Operation completed successfully"))
        else:
            self.show_error(self.tr("Operation failed (exit code {})").format(exit_code))


# ---------------------------------------------------------------------------
# Main consolidated tab
# ---------------------------------------------------------------------------


class SoftwareTab(BaseTab):
    """Consolidated software tab merging Applications and Repositories.

    Stable routes select pages in a stack owned by the application shell.
    """

    _METADATA = plugin_metadata_for_module(__name__)

    actionCenterRequested = pyqtSignal(str, object)

    def metadata(self: typing.Any) -> PluginMetadata:
        return typing.cast(PluginMetadata, self._METADATA)

    def create_widget(self) -> QWidget:
        return self

    def __init__(self: typing.Any) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QStackedWidget()
        self.tabs.setObjectName("softwareRouteStack")
        self._applications_tab = _ApplicationsSubTab()
        self._applications_tab.actionCenterRequested.connect(self.actionCenterRequested.emit)
        self.tabs.addWidget(self._applications_tab)
        self._repositories_tab = _RepositoriesSubTab()
        self._repositories_tab.actionCenterRequested.connect(self.actionCenterRequested.emit)
        self.tabs.addWidget(self._repositories_tab)
        self.tabs.addWidget(self._create_flatpak_tab())
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self._route_active = False

        layout.addWidget(self.tabs)

    def on_activate(self: typing.Any) -> None:
        self._route_active = True
        QTimer.singleShot(0, self._activate_current_subtab)

    def on_deactivate(self: typing.Any) -> None:
        self._route_active = False

    def _on_tab_changed(self: typing.Any, _index: int) -> None:
        if self._route_active:
            self._activate_current_subtab()

    def _activate_current_subtab(self: typing.Any) -> None:
        if self._route_active and self.tabs.currentIndex() == 0:
            self._applications_tab.on_activate()

    def activate_route(self: typing.Any, route: typing.Any) -> bool:
        """Select a Software & Updates page from a stable route ID."""
        route_to_index = {
            "software": 0,
            "software:apps": 0,
            "software:repos": 1,
            "software:flatpak": 2,
        }
        index = route_to_index.get(str(getattr(route, "id", route)))
        if index is None:
            return False
        self.tabs.setCurrentIndex(index)
        self._on_tab_changed(index)
        return True

    def _create_flatpak_tab(self: typing.Any) -> typing.Any:
        """Create the Flatpak Manager sub-tab (v37.0 Pinnacle)."""

        widget = QWidget()
        root = QVBoxLayout(widget)
        root.setContentsMargins(0, 0, 0, 0)
        scaffold = PageScaffold(
            self.tr("Flatpak"),
            self.tr("Inspect Flatpak storage and permissions before running cleanup actions."),
        )
        root.addWidget(scaffold)
        layout = scaffold.content_layout

        # Size overview
        size_group = QGroupBox(self.tr("Flatpak Storage"))
        size_layout = QVBoxLayout(size_group)

        self._flatpak_size_label = QLabel(self.tr("Total size: calculating..."))
        size_layout.addWidget(self._flatpak_size_label)

        btn_row = QHBoxLayout()
        btn_sizes = QPushButton(self.tr("Show Sizes"))
        btn_sizes.setAccessibleName(self.tr("Show Flatpak sizes"))
        btn_sizes.clicked.connect(self._show_flatpak_sizes)
        btn_row.addWidget(btn_sizes)

        btn_orphans = QPushButton(self.tr("Find Orphan Runtimes"))
        btn_orphans.setAccessibleName(self.tr("Find orphan runtimes"))
        btn_orphans.clicked.connect(self._find_orphans)
        btn_row.addWidget(btn_orphans)

        btn_cleanup = QPushButton(self.tr("Cleanup Unused"))
        btn_cleanup.setAccessibleName(self.tr("Cleanup unused Flatpaks"))
        btn_cleanup.clicked.connect(self._cleanup_flatpaks)
        btn_row.addWidget(btn_cleanup)
        btn_row.addStretch()
        size_layout.addLayout(btn_row)

        layout.addWidget(size_group)

        # Permissions
        perm_group = QGroupBox(self.tr("Permissions Audit"))
        perm_layout = QVBoxLayout(perm_group)

        btn_perms = QPushButton(self.tr("Show App Permissions"))
        btn_perms.setAccessibleName(self.tr("Show Flatpak permissions"))
        btn_perms.clicked.connect(self._show_permissions)
        perm_layout.addWidget(btn_perms)

        self._flatpak_perms_list = QListWidget()
        self._flatpak_perms_list.setMinimumHeight(120)
        perm_layout.addWidget(self._flatpak_perms_list)

        layout.addWidget(perm_group)

        # Output
        self._flatpak_output = QTextEdit()
        self._flatpak_output.setReadOnly(True)
        self._flatpak_output.setMaximumHeight(120)
        self._flatpak_details = DetailsDisclosure(summary=self.tr("Show Flatpak command output"))
        self._flatpak_details.add_widget(self._flatpak_output)
        layout.addWidget(self._flatpak_details)

        self._flatpak_runner = CommandRunner()
        self._flatpak_runner.output_received.connect(lambda t: self._flatpak_output.insertPlainText(t))
        self._flatpak_runner.finished.connect(lambda ec: self._flatpak_output.insertPlainText(self.tr("\nDone (exit {})\n").format(ec)))

        layout.addStretch()
        return widget

    def _show_flatpak_sizes(self: typing.Any) -> typing.Any:
        try:
            from services.software import FlatpakManager

            sizes = FlatpakManager.get_flatpak_sizes()
            total = FlatpakManager.get_total_size()
            self._flatpak_size_label.setText(self.tr("Total size: {}").format(total))
            lines = [f"{s.app_id}: {s.size_str}" for s in sizes]
            self._flatpak_output.setPlainText("\n".join(lines) or "No Flatpaks found.")
        except (RuntimeError, OSError, ValueError) as e:
            self._flatpak_output.setPlainText(f"[ERROR] {e}")

    def _find_orphans(self: typing.Any) -> typing.Any:
        try:
            from services.software import FlatpakManager

            orphans = FlatpakManager.find_orphan_runtimes()
            lines = [str(orphan) for orphan in orphans]
            self._flatpak_output.setPlainText("\n".join(lines) if lines else "No orphan runtimes found.")
        except (RuntimeError, OSError, ValueError) as e:
            self._flatpak_output.setPlainText(f"[ERROR] {e}")

    def _cleanup_flatpaks(self: typing.Any) -> typing.Any:
        self.actionCenterRequested.emit("remove-unused-flatpaks", {})
        self._flatpak_output.setPlainText(self.tr("Review the exact Flatpak cleanup guidance in Action Center."))

    def _show_permissions(self: typing.Any) -> typing.Any:
        try:
            from services.software import FlatpakManager

            self._flatpak_perms_list.clear()
            all_perms = FlatpakManager.get_all_permissions()
            for app in all_perms:
                self._flatpak_perms_list.addItem(f"{app.app_id}: {len(app.permissions)} permissions")
            if not all_perms:
                self._flatpak_perms_list.addItem("No Flatpak apps found.")
        except (RuntimeError, OSError, ValueError) as e:
            self._flatpak_output.setPlainText(f"[ERROR] {e}")
