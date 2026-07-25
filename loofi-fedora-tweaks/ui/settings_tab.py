"""
Settings Tab - User-facing preferences UI.
Part of v13.5 "UX Polish" update.

Five stable subroutes selected by the application section navigator:
  Appearance, Behavior, Advanced Tools, Repair Loofi, and About.
"""

import platform

from core.navigation.models import NavigationMode
from core.plugins.interface import PluginInterface
from core.plugins.metadata import PluginMetadata
from core.product_catalog import plugin_metadata_for_module
from core.fedora_release_policy import FEDORA_RELEASE_POLICY
from PyQt6.QtCore import PYQT_VERSION_STR, QT_VERSION_STR
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFileDialog,
    QFrame,
    QGroupBox,
    QLabel,
    QMessageBox,
    QScrollArea,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from utils.settings import SettingsManager
from version import __app_name__, __version__, __version_codename__

from ui.components import ActionBar, DangerButton, PageScaffold, SecondaryButton


class SettingsTab(QWidget, PluginInterface):
    """Application settings, local state repair, and build information."""

    _METADATA = plugin_metadata_for_module(__name__)

    def __init__(self):
        super().__init__()
        self._main_window = None
        self._mgr = SettingsManager.instance()
        self._ui_initialized = False
        # Guard against headless/non-Qt execution paths that import tabs without a QApplication.
        if QApplication.instance() is not None:
            self._init_ui()

    def metadata(self) -> PluginMetadata:
        return self._METADATA

    def create_widget(self) -> QWidget:
        return self

    def set_context(self, context: dict) -> None:
        self._main_window = context.get("main_window")
        if not self._ui_initialized:
            self._init_ui()
        self._update_component_status()

    # ------------------------------------------------------------------ UI --

    def _init_ui(self):
        if self._ui_initialized:
            return
        self._ui_initialized = True

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        tabs = QStackedWidget()
        tabs.setObjectName("settingsRouteStack")
        tabs.addWidget(self._scaffold_page(
            self._build_appearance_tab(),
            self.tr("Appearance"),
            self.tr("Choose the application theme. Changes are saved automatically."),
        ))
        tabs.addWidget(self._scaffold_page(
            self._build_behavior_tab(),
            self.tr("Behavior"),
            self.tr("Configure startup, notifications, confirmations, and route restoration."),
        ))
        tabs.addWidget(self._scaffold_page(
            self._build_advanced_tab(),
            self.tr("Advanced Tools"),
            self.tr("Choose Standard or Advanced navigation without weakening safety checks."),
        ))
        tabs.addWidget(self._scaffold_page(
            self._build_state_tab(),
            self.tr("Repair Loofi"),
            self.tr("Inspect local state before exporting or resetting application data."),
        ))
        tabs.addWidget(self._scaffold_page(
            self._build_about_tab(),
            self.tr("About"),
            self.tr("Review application, runtime, support, and compatibility information."),
        ))
        self.settings_tabs = tabs
        outer.addWidget(tabs)

    @staticmethod
    def _scaffold_page(page: QWidget, accessible_name: str, description: str) -> QScrollArea:
        """Wrap one settings route in the shared bounded page scaffold."""
        scaffold = PageScaffold(accessible_name, description)
        scaffold.add_widget(page)
        scaffold.content_layout.addStretch()
        scroll = QScrollArea()
        scroll.setObjectName("settingsRouteScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(scaffold)
        return scroll

    def activate_route(self, route) -> bool:
        """Activate stable settings subroutes without relying on translated labels."""
        route_to_index = {
            "settings": 0,
            "settings:appearance": 0,
            "settings:behavior": 1,
            "settings:advanced": 2,
            "settings:repair": 3,
            "settings:about": 4,
        }
        index = route_to_index.get(str(getattr(route, "id", route)))
        if index is None:
            return False
        self.settings_tabs.setCurrentIndex(index)
        return True

    # --------------------------------------------------------- Appearance --

    def _build_appearance_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setSpacing(12)

        # Help text (v47.0)
        help_label = QLabel(self.tr(
            "Choose your visual theme. 'Follow system theme' auto-detects your desktop preference."
        ))
        help_label.setWordWrap(True)
        help_label.setObjectName("settingsHelpText")
        form.addRow(help_label)

        # Theme selector
        self.theme_combo = QComboBox()
        self.theme_combo.setAccessibleName(self.tr("Theme selector"))
        self.theme_combo.addItems(["dark", "light", "highcontrast"])
        self.theme_combo.setCurrentText(self._mgr.get("theme"))
        self.theme_combo.setEnabled(not self._mgr.get("follow_system_theme"))
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        form.addRow(self.tr("Theme:"), self.theme_combo)

        # Follow system theme
        self.follow_system_cb = QCheckBox(self.tr("Follow system theme"))
        self.follow_system_cb.setAccessibleName(self.tr("Follow system theme"))
        self.follow_system_cb.setChecked(self._mgr.get("follow_system_theme"))
        self.follow_system_cb.toggled.connect(self._on_follow_system_toggled)
        form.addRow("", self.follow_system_cb)

        # v29.0: Reset appearance to defaults
        reset_appearance_btn = SecondaryButton(self.tr("Reset Appearance"))
        reset_appearance_btn.setAccessibleName(self.tr("Reset Appearance"))
        reset_appearance_btn.setToolTip(self.tr("Reset theme settings to defaults"))
        reset_appearance_btn.clicked.connect(self._reset_appearance)
        appearance_actions = ActionBar()
        appearance_actions.add_action(reset_appearance_btn)
        form.addRow("", appearance_actions)

        return page

    # ----------------------------------------------------------- Behavior --

    def _build_behavior_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setSpacing(12)

        self.start_minimized_cb = QCheckBox(self.tr("Start minimized to tray"))
        self.start_minimized_cb.setAccessibleName(self.tr("Start minimized to tray"))
        self.start_minimized_cb.setChecked(self._mgr.get("start_minimized"))
        self.start_minimized_cb.toggled.connect(
            lambda v: self._toggle_setting("start_minimized", v)
        )
        form.addRow("", self.start_minimized_cb)

        self.notifications_cb = QCheckBox(self.tr("Show desktop notifications"))
        self.notifications_cb.setAccessibleName(self.tr("Show desktop notifications"))
        self.notifications_cb.setChecked(self._mgr.get("show_notifications"))
        self.notifications_cb.toggled.connect(
            lambda v: self._toggle_setting("show_notifications", v)
        )
        form.addRow("", self.notifications_cb)

        self.confirm_cb = QCheckBox(self.tr("Confirm dangerous actions"))
        self.confirm_cb.setAccessibleName(self.tr("Confirm dangerous actions"))
        self.confirm_cb.setChecked(self._mgr.get("confirm_dangerous_actions"))
        self.confirm_cb.toggled.connect(
            lambda v: self._toggle_setting("confirm_dangerous_actions", v)
        )
        form.addRow("", self.confirm_cb)

        self.restore_tab_cb = QCheckBox(self.tr("Restore last active tab on start"))
        self.restore_tab_cb.setAccessibleName(self.tr("Restore last active tab on start"))
        self.restore_tab_cb.setChecked(self._mgr.get("restore_last_tab"))
        self.restore_tab_cb.toggled.connect(
            lambda v: self._toggle_setting("restore_last_tab", v)
        )
        form.addRow("", self.restore_tab_cb)

        # v29.0: Reset behavior to defaults
        reset_behavior_btn = SecondaryButton(self.tr("Reset Behavior"))
        reset_behavior_btn.setAccessibleName(self.tr("Reset Behavior"))
        reset_behavior_btn.setToolTip(self.tr("Reset behavior settings to defaults"))
        reset_behavior_btn.clicked.connect(self._reset_behavior)
        behavior_actions = ActionBar()
        behavior_actions.add_action(reset_behavior_btn)
        form.addRow("", behavior_actions)

        return page

    # ----------------------------------------------------------- Advanced --

    def _build_advanced_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        # Help text (v47.0)
        help_label = QLabel(self.tr(
            "Advanced settings for debugging and maintenance. "
            "Only change these if you know what you're doing."
        ))
        help_label.setWordWrap(True)
        help_label.setObjectName("settingsHelpText")
        layout.addWidget(help_label)

        mode_group = QGroupBox(self.tr("Specialist Tools"))
        mode_form = QFormLayout(mode_group)
        self._mode_desc = QLabel(
            self.tr(
                "Specialist tools are always available. Each system change still has its own review and confirmation."
            )
        )
        self._mode_desc.setWordWrap(True)
        self._mode_desc.setObjectName("settingsHelpText")
        mode_form.addRow("", self._mode_desc)

        self._component_status = QLabel()
        self._component_status.setWordWrap(True)
        self._component_status.setObjectName("settingsHelpText")
        mode_form.addRow(self.tr("Components:"), self._component_status)
        self._update_component_status()
        layout.addWidget(mode_group)

        # Log level
        log_group = QGroupBox(self.tr("Logging"))
        log_form = QFormLayout(log_group)
        self.log_combo = QComboBox()
        self.log_combo.setAccessibleName(self.tr("Log level selector"))
        self.log_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.log_combo.setCurrentText(self._mgr.get("log_level"))
        self.log_combo.currentTextChanged.connect(self._on_log_level_changed)
        log_form.addRow(self.tr("Log level:"), self.log_combo)
        layout.addWidget(log_group)

        # Update checking
        self.updates_cb = QCheckBox(self.tr("Check for updates on start"))
        self.updates_cb.setAccessibleName(self.tr("Check for updates on start"))
        self.updates_cb.setChecked(self._mgr.get("check_updates_on_start"))
        self.updates_cb.toggled.connect(
            lambda v: self._toggle_setting("check_updates_on_start", v)
        )
        layout.addWidget(self.updates_cb)

        # Reset
        reset_group = QGroupBox(self.tr("Reset"))
        reset_layout = QVBoxLayout(reset_group)
        reset_btn = DangerButton(self.tr("Reset All Settings to Defaults"))
        reset_btn.setAccessibleName(self.tr("Reset All Settings to Defaults"))
        reset_btn.clicked.connect(self._on_reset)
        reset_actions = ActionBar()
        reset_actions.add_action(reset_btn, primary=True)
        reset_layout.addWidget(reset_actions)
        layout.addWidget(reset_group)

        layout.addStretch()
        return page

    def _build_state_tab(self) -> QWidget:
        """Repair Loofi presentation over the unchanged v14 state services."""
        page = QWidget()
        layout = QVBoxLayout(page)
        intro = QLabel(self.tr(
            "Repair Loofi checks local files, schemas, locks, permissions, and collector freshness. "
            "The check is read-only. This page repairs and archives Loofi application state only; "
            "it does not create system recovery points, personal-file backups, rollback deployments, "
            "or support bundles. State backups exclude credentials, raw logs, plugin code, and caches."
        ))
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.state_status = QTextEdit()
        self.state_status.setReadOnly(True)
        self.state_status.setAccessibleName(self.tr("Repair Loofi results"))
        self.state_status.setPlainText(self.tr("Select Inspect Loofi State to run the read-only check."))
        layout.addWidget(self.state_status)
        doctor_button = SecondaryButton(self.tr("Inspect Loofi State"))
        doctor_button.clicked.connect(self._run_state_doctor)
        backup_button = SecondaryButton(self.tr("Create Privacy-Safe Backup…"))
        backup_button.clicked.connect(self._create_state_backup)
        restore_button = SecondaryButton(self.tr("Preview State Restore…"))
        restore_button.clicked.connect(self._preview_state_restore)
        state_actions = ActionBar()
        state_actions.add_action(doctor_button)
        state_actions.add_action(backup_button)
        state_actions.add_action(restore_button)
        layout.addWidget(state_actions)
        layout.addStretch()
        return page

    def _build_about_tab(self) -> QWidget:
        """Build static version, runtime, and support information."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        form = QFormLayout()
        form.addRow(self.tr("Application:"), QLabel(__app_name__))
        form.addRow(self.tr("Version:"), QLabel(__version__))
        form.addRow(self.tr("Build identity:"), QLabel(__version_codename__))
        form.addRow(self.tr("Python:"), QLabel(platform.python_version()))
        form.addRow(self.tr("Qt:"), QLabel(QT_VERSION_STR))
        form.addRow(self.tr("PyQt:"), QLabel(PYQT_VERSION_STR))
        layout.addLayout(form)

        support = QLabel(
            self.tr("Fedora %s is the supported target. Fedora %s remains preview/advisory and capability-aware.")
            % (FEDORA_RELEASE_POLICY.stable_release, FEDORA_RELEASE_POLICY.preview_release)
        )
        support.setObjectName("settingsHelpText")
        support.setWordWrap(True)
        layout.addWidget(support)

        links = QLabel(
            '<a href="https://github.com/loofiboss-bit/loofi-fedora-tweaks/wiki">Documentation</a>'
            ' · <a href="https://github.com/loofiboss-bit/loofi-fedora-tweaks/issues">Support and issues</a>'
        )
        links.setAccessibleName(self.tr("Documentation and support links"))
        links.setOpenExternalLinks(True)
        layout.addWidget(links)
        layout.addStretch()
        return page

    def _run_state_doctor(self):
        from core.state import StateDoctor

        result = StateDoctor().run()
        lines = [self.tr("Overall status: %s") % result["status"], self.tr("Registered domains: %d") % len(result["domains"])]
        for finding in result["findings"]:
            lines.append(f"[{finding['severity'].upper()}] {finding['domain']}: {finding['summary']}\n  {finding['next_step']}")
        if not result["findings"]:
            lines.append(self.tr("No state integrity problems found."))
        self.state_status.setPlainText("\n".join(lines))

    def _create_state_backup(self):
        from pathlib import Path
        from core.state import StateArchiveService

        destination, _ = QFileDialog.getSaveFileName(self, self.tr("Create State Backup"), "loofi-state.zip", self.tr("ZIP archive (*.zip)"))
        if not destination:
            return
        manifest = StateArchiveService().backup(Path(destination))
        self.state_status.setPlainText(self.tr("Backup created: %s\nIncluded domains: %d") % (destination, len(manifest["entries"])))

    def _preview_state_restore(self, archive_path: str = ""):
        from pathlib import Path
        from core.state import StateArchiveService

        source = archive_path
        if not source:
            source, _ = QFileDialog.getOpenFileName(self, self.tr("Preview State Restore"), "", self.tr("ZIP archive (*.zip)"))
        if not source:
            return
        plan = StateArchiveService().plan_restore(Path(source))
        lines = [self.tr("Restore preview — no state has changed."), self.tr("Plan ID: %s") % plan["plan_id"]]
        lines.extend(f"{action['status'].upper()}: {action['domain']} → {action['target']}" for action in plan["actions"])
        self.state_status.setPlainText("\n".join(lines))

    def _show_collector_status(self):
        from core.observability import ObservabilityService

        status = ObservabilityService().status(source="gui")
        self.state_status.setPlainText(self.tr(
            "Collector status\nOwner: %s\nSnapshots: %d\nFreshness: %s\nRecovery: %s"
        ) % (status.collector_owner, status.snapshot_count, status.freshness_seconds, status.recovery_status))

    # ------------------------------------------------------------ Slots --

    def _mode_description(self, mode: NavigationMode) -> str:
        """Return a concise description for the canonical navigation mode."""
        descriptions = {
            NavigationMode.STANDARD: self.tr(
                "Standard keeps normal Fedora maintenance focused on the six core destinations."
            ),
            NavigationMode.ADVANCED: self.tr(
                "Advanced adds specialist routes without changing confirmations or safety rules."
            ),
        }
        return str(descriptions.get(mode, ""))

    def _on_navigation_mode_changed(self, index: int):
        """Persist and immediately apply Standard or Advanced mode."""
        from utils.navigation_mode import NavigationModeManager

        mode = NavigationMode.ADVANCED if index == 1 else NavigationMode.STANDARD
        NavigationModeManager.set_mode(mode)
        self._mode_desc.setText(self._mode_description(mode))
        if self._main_window and hasattr(self._main_window, "apply_navigation_mode"):
            self._main_window.apply_navigation_mode(mode)

    def _update_component_status(self) -> None:
        """Explain logical component availability without installing anything."""
        label = getattr(self, "_component_status", None)
        if label is None:
            return
        context = getattr(self._main_window, "_navigation_context", None)
        installed = getattr(context, "installed_components", frozenset({"core", "specialist"}))
        if "specialist" in installed:
            text = self.tr(
                "Core and specialist tools are included in this build. Changing mode never installs packages."
            )
        else:
            text = self.tr(
                "This build does not include specialist tools. Your distribution may provide them as an optional component."
            )
        label.setText(text)

    def _on_theme_changed(self, theme_name: str):
        self._mgr.set("theme", theme_name)
        self._mgr.save()
        if (
            not self._mgr.get("follow_system_theme")
            and self._main_window
            and hasattr(self._main_window, "load_theme")
        ):
            self._main_window.load_theme(theme_name)

    def _on_follow_system_toggled(self, checked: bool):
        self._mgr.set("follow_system_theme", checked)
        self._mgr.save()
        self.theme_combo.setEnabled(not checked)
        if self._main_window and hasattr(self._main_window, "load_theme"):
            self._main_window.load_theme("system" if checked else self.theme_combo.currentText())

    def _toggle_setting(self, key: str, value: bool):
        self._mgr.set(key, value)
        self._mgr.save()

    def _on_log_level_changed(self, level: str):
        self._mgr.set("log_level", level)
        self._mgr.save()

    def _on_reset(self):
        reply = QMessageBox.question(
            self,
            self.tr("Reset Settings"),
            self.tr(
                "This will restore all settings to their default values. Continue?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._mgr.reset()

        # Refresh widgets to reflect defaults
        self.theme_combo.setCurrentText(self._mgr.get("theme"))
        self.follow_system_cb.setChecked(self._mgr.get("follow_system_theme"))
        self.start_minimized_cb.setChecked(self._mgr.get("start_minimized"))
        self.notifications_cb.setChecked(self._mgr.get("show_notifications"))
        self.confirm_cb.setChecked(self._mgr.get("confirm_dangerous_actions"))
        self.restore_tab_cb.setChecked(self._mgr.get("restore_last_tab"))
        self.log_combo.setCurrentText(self._mgr.get("log_level"))
        self.updates_cb.setChecked(self._mgr.get("check_updates_on_start"))
        self._sync_mode_controls()

        if self._main_window and hasattr(self._main_window, "load_theme"):
            selected = "system" if self._mgr.get("follow_system_theme") else self._mgr.get("theme")
            self._main_window.load_theme(selected)

    # ---------------------------------------- v29.0 Reset per group --

    def _reset_appearance(self):
        """Reset appearance settings to defaults."""
        self._mgr.reset_group(["theme", "follow_system_theme"])
        self.theme_combo.setCurrentText(self._mgr.get("theme"))
        self.follow_system_cb.setChecked(self._mgr.get("follow_system_theme"))
        if self._main_window and hasattr(self._main_window, "load_theme"):
            selected = "system" if self._mgr.get("follow_system_theme") else self._mgr.get("theme")
            self._main_window.load_theme(selected)

    def _reset_behavior(self):
        """Reset behavior settings to defaults."""
        self._mgr.reset_group([
            "start_minimized", "show_notifications",
            "confirm_dangerous_actions", "restore_last_tab", "last_tab_index",
        ])
        self.start_minimized_cb.setChecked(self._mgr.get("start_minimized"))
        self.notifications_cb.setChecked(self._mgr.get("show_notifications"))
        self.confirm_cb.setChecked(self._mgr.get("confirm_dangerous_actions"))
        self.restore_tab_cb.setChecked(self._mgr.get("restore_last_tab"))

    def _sync_mode_controls(self) -> None:
        """Compatibility hook after reset; v20 has no global mode control."""
        self._mode_desc.setText(
            self.tr(
                "Specialist tools are always available. Each system change still has its own review and confirmation."
            )
        )
