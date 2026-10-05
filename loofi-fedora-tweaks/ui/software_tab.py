"""
Software Tab - Consolidated tab merging Applications and Repositories.
Part of v11.0 "Aurora Update".

Uses a route-owned stack so the application shell remains the only owner of
section navigation.
"""

from __future__ import annotations

import typing
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.software.source_status import SourceScope, SourceStatus
    from ui.operation_worker import OperationControllerQtAdapter

from core.catalog_models import NativeHandoffId
from core.plugins.metadata import PluginMetadata
from core.product_catalog import plugin_metadata_for_module
from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from utils.command_runner import CommandRunner

from ui.base_tab import BaseTab
from ui.components import (
    DetailsDisclosure,
    PageScaffold,
)
from ui.native_handoff_card import NativeHandoffCard
from ui.shared_states import EmptyState
from ui.tooltips import (
    SW_CODECS,
    SW_FLATHUB,
    SW_RPM_FUSION,
)


# ---------------------------------------------------------------------------
# Sub-tab: Applications
# ---------------------------------------------------------------------------


class _ApplicationsSubTab(BaseTab):
    """Hand application discovery to the desktop's native software center.

    Fedora desktops already own AppStream discovery, package provenance,
    permissions, updates, and uninstall semantics.  Keeping a second remote
    catalogue here made the product desktop-specific and created a second
    package mutation path.  This page is intentionally a read-only handoff.
    """

    # Keep the signal for the consolidated tab's stable plugin interface.  No
    # application install/remove action is emitted from this view.
    actionCenterRequested = pyqtSignal(str, object)

    def __init__(self: typing.Any) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scaffold = PageScaffold(
            self.tr("Applications"),
            self.tr("Use the software center provided by your desktop environment."),
        )
        root.addWidget(self.scaffold)
        layout = self.scaffold.content_layout

        self.native_handoff = NativeHandoffCard(
            NativeHandoffId.SOFTWARE_CENTER,
            title=self.tr("Open the software center"),
            description=self.tr(
                "Search, install, update, and remove applications in the native "
                "AppStream software center. Loofi does not mirror or mutate its catalogue."
            ),
            button_text=self.tr("Open Software Store"),
        )
        layout.addWidget(self.native_handoff)

        self.catalog_empty = EmptyState(
            self.tr("Application management is delegated"),
            self.tr(
                "The available software center is detected for this desktop. "
                "If no handoff is available, use the desktop's documented package workflow."
            ),
        )
        self.catalog_empty.setProperty("handoffOnly", True)
        layout.addWidget(self.catalog_empty)
        layout.addStretch()

        # Compatibility state for callers that used to trigger a refresh.  It
        # is deliberately inert and never starts a remote request.
        self.apps: list[object] = []

    def on_activate(self: typing.Any) -> None:
        """Refresh only native availability when the route is shown."""
        self.native_handoff.refresh_availability()

    def refresh_list(self: typing.Any) -> None:
        """Compatibility no-op; the native store owns its application list."""
        self.native_handoff.refresh_availability()

    def load_apps(self: typing.Any) -> list[object]:
        """Return no local catalogue; retained for old embedders as a no-op."""
        return []


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
        # Keep service imports lazy so importing this UI module does not
        # initialize software services in lightweight embedders.
        from services.software import source_status

        self._source_status_api = source_status
        self._source_status_service = source_status.SoftwareSourceStatusService()
        self._source_status_adapter: OperationControllerQtAdapter | None = None
        self._source_status_labels: dict[tuple[str, SourceScope], QLabel] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scaffold = PageScaffold(
            self.tr("Repositories"),
            self.tr("Check locally configured software sources. Setup and codec installation remain guided manual steps."),
        )
        root.addWidget(self.scaffold)
        layout = self.scaffold.content_layout

        self.source_status_note = QLabel(
            self.tr("Status describes local configuration only; it does not check source availability or trust.")
        )
        self.source_status_note.setWordWrap(True)
        self.source_status_note.setAccessibleName(self.tr("About software source status"))
        layout.addWidget(self.source_status_note)

        # RPM Fusion Group
        fusion_group = QGroupBox(self.tr("RPM Fusion"))
        fusion_layout = QVBoxLayout()
        fusion_group.setLayout(fusion_layout)

        fusion_layout.addWidget(self._new_source_status_label("rpmfusion-free", self._source_status_api.SourceScope.SYSTEM))
        fusion_layout.addWidget(self._new_source_status_label("rpmfusion-nonfree", self._source_status_api.SourceScope.SYSTEM))

        self.btn_rpm_fusion_guidance = QPushButton(self.tr("View RPM Fusion setup instructions"))
        self.btn_rpm_fusion_guidance.setObjectName("rpmFusionSetupGuidance")
        self.btn_rpm_fusion_guidance.setAccessibleName(self.tr("View RPM Fusion setup instructions"))
        self.btn_rpm_fusion_guidance.setToolTip(SW_RPM_FUSION)
        self.btn_rpm_fusion_guidance.clicked.connect(self.show_rpm_fusion_guidance)
        fusion_layout.addWidget(self.btn_rpm_fusion_guidance)

        self.btn_codec_guidance = QPushButton(self.tr("View multimedia codec installation instructions"))
        self.btn_codec_guidance.setObjectName("codecSetupGuidance")
        self.btn_codec_guidance.setAccessibleName(self.tr("View codec installation instructions"))
        self.btn_codec_guidance.setToolTip(SW_CODECS)
        self.btn_codec_guidance.clicked.connect(self.show_codec_guidance)
        fusion_layout.addWidget(self.btn_codec_guidance)

        layout.addWidget(fusion_group)

        # Flatpak Flathub
        flathub_group = QGroupBox(self.tr("Flathub (Flatpak)"))
        flathub_layout = QVBoxLayout()
        flathub_group.setLayout(flathub_layout)

        flathub_layout.addWidget(self._new_source_status_label("flathub", self._source_status_api.SourceScope.SYSTEM))
        flathub_layout.addWidget(self._new_source_status_label("flathub", self._source_status_api.SourceScope.USER))

        self.btn_flathub_guidance = QPushButton(self.tr("View Flathub setup instructions"))
        self.btn_flathub_guidance.setObjectName("flathubSetupGuidance")
        self.btn_flathub_guidance.setAccessibleName(self.tr("View Flathub setup instructions"))
        self.btn_flathub_guidance.setToolTip(SW_FLATHUB)
        self.btn_flathub_guidance.clicked.connect(self.show_flathub_guidance)
        flathub_layout.addWidget(self.btn_flathub_guidance)

        layout.addWidget(flathub_group)

        # COPR Repos Section
        copr_group = QGroupBox(self.tr("COPR Repositories"))
        copr_layout = QVBoxLayout()
        copr_group.setLayout(copr_layout)

        copr_layout.addWidget(QLabel(self.tr("Common COPR Repositories:")))

        copr_layout.addWidget(self._new_source_status_label("loofi-copr", self._source_status_api.SourceScope.SYSTEM))

        self.btn_loofi_copr_guidance = QPushButton(self.tr("View Loofi COPR setup instructions"))
        self.btn_loofi_copr_guidance.setObjectName("loofiCoprSetupGuidance")
        self.btn_loofi_copr_guidance.setAccessibleName(self.tr("View Loofi COPR setup instructions"))
        self.btn_loofi_copr_guidance.clicked.connect(self.show_loofi_copr_guidance)
        copr_layout.addWidget(self.btn_loofi_copr_guidance)

        layout.addWidget(copr_group)

        # Output Area
        self.output_area = QTextEdit()
        self.output_area.setReadOnly(True)
        self.output_area.setMaximumHeight(200)
        self.output_details = DetailsDisclosure(summary=self.tr("Show repository command output"))
        self.output_details.add_widget(self.output_area)
        layout.addWidget(self.output_details)

        self.refresh_source_status_button = QPushButton(self.tr("Refresh source status"))
        self.refresh_source_status_button.setObjectName("refreshSourceStatus")
        self.refresh_source_status_button.setAccessibleName(self.tr("Refresh software source status"))
        self.refresh_source_status_button.clicked.connect(self.refresh_source_status)
        layout.addWidget(self.refresh_source_status_button)

    # -- Repository actions ------------------------------------------------

    def show_rpm_fusion_guidance(self: typing.Any) -> None:
        self.actionCenterRequested.emit("enable-rpm-fusion", {})

    def show_codec_guidance(self: typing.Any) -> None:
        self.actionCenterRequested.emit("install-multimedia-codecs", {})

    def show_flathub_guidance(self: typing.Any) -> None:
        self.actionCenterRequested.emit("enable-flathub", {})

    def show_loofi_copr_guidance(self: typing.Any) -> None:
        self.actionCenterRequested.emit("enable-loofi-copr", {})

    def on_activate(self: typing.Any) -> None:
        """Refresh local source status when the repositories route is opened."""
        self.refresh_source_status()

    def refresh_source_status(self: typing.Any) -> None:
        if self._source_status_adapter is None:
            from ui.operation_worker import OperationControllerQtAdapter

            self._source_status_adapter = OperationControllerQtAdapter(parent=self)
            self._source_status_adapter.finished.connect(self._apply_source_statuses)
            self._source_status_adapter.failed.connect(self._on_source_status_failed)
        if self._source_status_adapter.busy:
            return
        for label in self._source_status_labels.values():
            label.setText(self.tr("Checking source status…"))
            label.setAccessibleDescription(self.tr("Checking source status"))
            label.setProperty("sourceState", self._source_status_api.SourceState.UNKNOWN.value)
        self._source_status_adapter.start(self._source_status_service.snapshot)

    def _new_source_status_label(self: typing.Any, source_id: str, scope: SourceScope) -> QLabel:
        label = QLabel(self.tr("Status not checked yet"))
        label.setObjectName(f"sourceStatus:{source_id}:{scope.value}")
        label.setWordWrap(True)
        label.setProperty("sourceState", self._source_status_api.SourceState.UNKNOWN.value)
        source_name = {
            "rpmfusion-free": self.tr("RPM Fusion Free"),
            "rpmfusion-nonfree": self.tr("RPM Fusion Non-Free"),
            "loofi-copr": self.tr("Loofi COPR"),
            "flathub": self.tr("Flathub"),
        }.get(source_id, self.tr("Software source"))
        label.setAccessibleName(self.tr("{source} {scope} software source status").format(
            source=source_name,
            scope=self.tr(scope.value),
        ))
        label.setAccessibleDescription(self.tr("Status not checked yet"))
        self._source_status_labels[(source_id, scope)] = label
        return label

    def _apply_source_statuses(self: typing.Any, result: object) -> None:
        statuses = result if isinstance(result, (tuple, list)) else ()
        by_key = {
            (status.source_id, status.scope): status
            for status in statuses
            if isinstance(status, self._source_status_api.SourceStatus)
        }
        for key, label in self._source_status_labels.items():
            status = by_key.get(key)
            if status is None:
                status = self._source_status_api.SourceStatus(
                    key[0],
                    key[1],
                    self._source_status_api.SourceState.UNKNOWN,
                    self._source_status_api.SourceStatusReason.PROBE_FAILED,
                )
            self._render_source_status(label, status)

    def _on_source_status_failed(self: typing.Any, _message: str) -> None:
        self._apply_source_statuses(
            tuple(
                self._source_status_api.SourceStatus(
                    source_id,
                    scope,
                    self._source_status_api.SourceState.UNKNOWN,
                    self._source_status_api.SourceStatusReason.PROBE_FAILED,
                )
                for source_id, scope in self._source_status_api.SOURCE_STATUS_KEYS
            )
        )

    def _render_source_status(self: typing.Any, label: QLabel, status: SourceStatus) -> None:
        source_names = {
            "rpmfusion-free": self.tr("RPM Fusion Free"),
            "rpmfusion-nonfree": self.tr("RPM Fusion Non-Free"),
            "loofi-copr": self.tr("Loofi COPR"),
            "flathub": self.tr("Flathub"),
        }
        scope_names = {
            self._source_status_api.SourceScope.SYSTEM: self.tr("system"),
            self._source_status_api.SourceScope.USER: self.tr("user"),
        }
        state_names = {
            self._source_status_api.SourceState.ENABLED: self.tr("Enabled"),
            self._source_status_api.SourceState.DISABLED: self.tr("Not enabled"),
            self._source_status_api.SourceState.UNKNOWN: self.tr("Could not check"),
        }
        source_name = source_names.get(status.source_id, self.tr("Software source"))
        scope_name = scope_names[status.scope]
        state_name = state_names[status.state]
        text = self.tr("{source} ({scope}): {state}").format(
            source=source_name,
            scope=scope_name,
            state=state_name,
        )
        if status.state is self._source_status_api.SourceState.UNKNOWN:
            reason_messages = {
                self._source_status_api.SourceStatusReason.TOOL_UNAVAILABLE: self.tr("The required tool is not installed."),
                self._source_status_api.SourceStatusReason.UNSUPPORTED_BACKEND: self.tr(
                    "Repository status is not available for this Fedora deployment."
                ),
                self._source_status_api.SourceStatusReason.TIMEOUT: self.tr("The source status check timed out."),
                self._source_status_api.SourceStatusReason.COMMAND_FAILED: self.tr("The source list could not be read (exit code {code}).").format(
                    code=status.exit_code if status.exit_code is not None else self.tr("unknown")
                ),
                self._source_status_api.SourceStatusReason.INVALID_RESPONSE: self.tr("The tool returned an invalid source list."),
                self._source_status_api.SourceStatusReason.PROBE_FAILED: self.tr("The source configuration could not be inspected."),
            }
            reason = status.reason or self._source_status_api.SourceStatusReason.PROBE_FAILED
            text = self.tr("{status} {reason}").format(
                status=text,
                reason=reason_messages.get(reason, self.tr("The source configuration could not be inspected.")),
            )
        label.setText(text)
        label.setProperty("sourceState", status.state.value)
        label.setAccessibleName(self.tr("{source} {scope} source status: {state}").format(
            source=source_name,
            scope=scope_name,
            state=state_name,
        ))
        label.setAccessibleDescription(text)

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
        if not self._route_active:
            return
        if self.tabs.currentIndex() == 0:
            self._applications_tab.on_activate()
        elif self.tabs.currentIndex() == 1:
            self._repositories_tab.on_activate()

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
        """Create the Flatpak Manager sub-tab."""

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
