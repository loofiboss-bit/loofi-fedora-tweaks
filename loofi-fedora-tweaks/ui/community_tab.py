"""Local profiles, private sync, and quarantined legacy extension inventory."""

from __future__ import annotations

from pathlib import Path

from core.plugins.interface import PluginInterface
from core.plugins.legacy import LegacyExtensionService
from core.plugins.metadata import PluginMetadata
from core.product_catalog import plugin_metadata_for_module
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from services.storage import CloudSyncManager
from ui.components import InlineNotice, PageScaffold
from utils.config_manager import ConfigManager
from utils.presets import PresetManager


class CommunityTab(QWidget, PluginInterface):
    """Built-in local profile surface; no public catalog or executable code."""

    _METADATA = plugin_metadata_for_module(__name__)
    actionCenterRequested = pyqtSignal(str, object)

    def __init__(self) -> None:
        super().__init__()
        self.manager = PresetManager()
        self.sub_tabs = QStackedWidget()
        self._build_ui()

    def metadata(self) -> PluginMetadata:
        return self._METADATA

    def create_widget(self) -> QWidget:
        return self

    def on_activate(self) -> None:
        self.refresh_list()
        self.refresh_legacy_extensions()
        self.update_sync_status()

    def activate_route(self, route) -> bool:
        route_id = str(getattr(route, "id", route))
        if route_id not in {
            "community",
            "community:presets",
            "community:marketplace",
            "community:plugins",
            "community:featured",
        }:
            return False
        if route_id in {"community:marketplace", "community:plugins", "community:featured"}:
            self.retirement_banner.setVisible(True)
        self.sub_tabs.setCurrentIndex(0)
        return True

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self.sub_tabs)
        self.sub_tabs.addWidget(self._build_profiles_page())
        self.sub_tabs.addWidget(self._build_sync_page())
        self.sub_tabs.addWidget(self._build_legacy_page())

    def _build_profiles_page(self) -> PageScaffold:
        page = PageScaffold(
            self.tr("Local profiles"),
            self.tr("Capture settings locally and review changes before applying them."),
        )
        self.retirement_banner = InlineNotice(
            self.tr("Marketplace retired"),
            self.tr("Public presets and executable third-party plugins are no longer downloaded. Existing files remain untouched."),
            kind="warning",
        )
        self.retirement_banner.setVisible(False)
        page.add_widget(self.retirement_banner)

        self.list_widget = QListWidget()
        self.list_widget.setAccessibleName(self.tr("Local profiles"))
        page.add_widget(self.list_widget, 1)

        row = QHBoxLayout()
        save_button = QPushButton(self.tr("Save current profile"))
        save_button.clicked.connect(self.save_preset)
        import_button = QPushButton(self.tr("Import local profile"))
        import_button.clicked.connect(self.import_preset)
        review_button = QPushButton(self.tr("Review profile"))
        review_button.clicked.connect(self.load_preset)
        delete_button = QPushButton(self.tr("Delete local profile"))
        delete_button.clicked.connect(self.delete_preset)
        row.addWidget(save_button)
        row.addWidget(import_button)
        row.addWidget(review_button)
        row.addWidget(delete_button)
        row.addStretch()
        page.add_layout(row)

        self.profile_details = QTextEdit()
        self.profile_details.setReadOnly(True)
        self.profile_details.setAccessibleName(self.tr("Profile review"))
        self.profile_details.setPlaceholderText(
            self.tr("Select a local profile to review its settings. Host changes are never applied from this page.")
        )
        page.add_widget(self.profile_details)

        nav = QHBoxLayout()
        sync_button = QPushButton(self.tr("Private backup"))
        sync_button.clicked.connect(lambda: self.sub_tabs.setCurrentIndex(1))
        legacy_button = QPushButton(self.tr("Legacy extensions"))
        legacy_button.clicked.connect(lambda: self.sub_tabs.setCurrentIndex(2))
        nav.addWidget(sync_button)
        nav.addWidget(legacy_button)
        nav.addStretch()
        page.add_layout(nav)
        return page

    def _build_sync_page(self) -> PageScaffold:
        page = PageScaffold(
            self.tr("Private backup"),
            self.tr("Store your own configuration in a private GitHub Gist. No public discovery is performed."),
        )
        self.lbl_sync_status = QLabel()
        page.add_widget(self.lbl_sync_status)
        self.txt_token = QLineEdit()
        self.txt_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_token.setPlaceholderText(self.tr("GitHub token with Gist access"))
        page.add_widget(self.txt_token)
        row = QHBoxLayout()
        save_token = QPushButton(self.tr("Store token"))
        save_token.clicked.connect(self.save_token)
        push = QPushButton(self.tr("Back up now"))
        push.clicked.connect(self.push_to_gist)
        pull = QPushButton(self.tr("Download backup"))
        pull.clicked.connect(self.pull_from_gist)
        back = QPushButton(self.tr("Back to profiles"))
        back.clicked.connect(lambda: self.sub_tabs.setCurrentIndex(0))
        for button in (save_token, push, pull, back):
            row.addWidget(button)
        row.addStretch()
        page.add_layout(row)
        return page

    def _build_legacy_page(self) -> PageScaffold:
        page = PageScaffold(
            self.tr("Legacy extensions"),
            self.tr("External code is quarantined and never imported. Files remain available for manual inspection or export."),
        )
        self.legacy_list = QListWidget()
        self.legacy_list.setAccessibleName(self.tr("Quarantined legacy extensions"))
        page.add_widget(self.legacy_list, 1)
        row = QHBoxLayout()
        refresh = QPushButton(self.tr("Refresh inventory"))
        refresh.clicked.connect(self.refresh_legacy_extensions)
        export = QPushButton(self.tr("Export inventory"))
        export.clicked.connect(self.export_legacy_inventory)
        back = QPushButton(self.tr("Back to profiles"))
        back.clicked.connect(lambda: self.sub_tabs.setCurrentIndex(0))
        row.addWidget(refresh)
        row.addWidget(export)
        row.addWidget(back)
        row.addStretch()
        page.add_layout(row)
        return page

    def refresh_list(self) -> None:
        self.list_widget.clear()
        self.list_widget.addItems(self.manager.list_presets())

    def save_preset(self) -> None:
        name, accepted = QInputDialog.getText(self, self.tr("Save profile"), self.tr("Profile name:"))
        if not accepted or not name.strip():
            return
        if self.manager.save_preset(name.strip()):
            self.refresh_list()
            QMessageBox.information(self, self.tr("Profile saved"), self.tr("The profile was saved locally."))
        else:
            QMessageBox.warning(self, self.tr("Save failed"), self.tr("The local profile could not be saved."))

    def load_preset(self) -> None:
        item = self.list_widget.currentItem()
        if item is None:
            QMessageBox.warning(self, self.tr("Select a profile"), self.tr("Choose a local profile to review."))
            return
        data = self.manager.load_preset(item.text())
        if not isinstance(data, dict):
            QMessageBox.warning(self, self.tr("Profile unavailable"), self.tr("The profile could not be read."))
            return
        lines = [self.tr("Review only — no host settings were changed."), ""]
        lines.extend(f"{key}: {value}" for key, value in sorted(data.items()))
        self.profile_details.setPlainText("\n".join(lines))

    def import_preset(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Import local profile"),
            "",
            self.tr("JSON Files (*.json)"),
        )
        if not path:
            return
        success, detail = self.manager.import_preset(path)
        if not success:
            QMessageBox.warning(self, self.tr("Import rejected"), detail)
            return
        try:
            plan = self.manager.create_review_plan(detail)
            settings = self.manager.load_preset(detail)
        except (OSError, TypeError, ValueError) as exc:
            QMessageBox.warning(self, self.tr("Plan failed"), str(exc))
            return
        self.refresh_list()
        self.profile_details.setPlainText(
            self.tr("Imported as Action Center plan %1. No host setting was applied.").replace("%1", plan.plan_id)
        )
        self.actionCenterRequested.emit(
            "local-profile-review",
            {"profile": detail, "settings": settings},
        )

    def delete_preset(self) -> None:
        item = self.list_widget.currentItem()
        if item is None:
            return
        answer = QMessageBox.question(
            self,
            self.tr("Delete local profile"),
            self.tr("Delete %1? This removes only Loofi-local data.").replace("%1", item.text()),
        )
        if answer == QMessageBox.StandardButton.Yes and self.manager.delete_preset(item.text()):
            self.refresh_list()

    def save_token(self) -> None:
        token = self.txt_token.text().strip()
        valid_prefix = token.startswith(("ghp_", "github_pat_"))
        if not valid_prefix or len(token) < 12:
            QMessageBox.warning(self, self.tr("Invalid token"), self.tr("Enter a GitHub token with Gist access."))
            return
        if CloudSyncManager.save_gist_token(token):
            self.txt_token.clear()
            self.update_sync_status()
            QMessageBox.information(self, self.tr("Token stored"), self.tr("The token is stored in Secret Service or for this session only."))
        else:
            QMessageBox.warning(self, self.tr("Token not stored"), self.tr("Credential storage rejected the token."))

    def update_sync_status(self) -> None:
        if CloudSyncManager.get_gist_token():
            self.lbl_sync_status.setText(self.tr("Connected for private backup"))
        else:
            self.lbl_sync_status.setText(self.tr("Not configured — no token is stored"))

    def push_to_gist(self) -> None:
        if not CloudSyncManager.get_gist_token():
            QMessageBox.warning(self, self.tr("Token required"), self.tr("Store a GitHub token first."))
            return
        success, message = CloudSyncManager.sync_to_gist(ConfigManager.export_all())
        method = QMessageBox.information if success else QMessageBox.warning
        method(self, self.tr("Private backup"), str(message))

    def pull_from_gist(self) -> None:
        success, payload = CloudSyncManager.sync_from_gist()
        if not success or not isinstance(payload, dict):
            QMessageBox.warning(self, self.tr("Download failed"), str(payload))
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Save downloaded profile"),
            "loofi-private-backup.json",
            self.tr("JSON Files (*.json)"),
        )
        if not path:
            return
        from core.state.atomic_io import atomic_write_json

        atomic_write_json(Path(path), payload, mode=0o600, keep_backup=False)
        QMessageBox.information(
            self,
            self.tr("Backup downloaded"),
            self.tr("The backup was saved for review. Host settings were not applied."),
        )

    def refresh_legacy_extensions(self) -> None:
        self.legacy_list.clear()
        records = LegacyExtensionService.list_extensions()
        if not records:
            self.legacy_list.addItem(self.tr("No legacy extension directories found."))
            return
        for record in records:
            suffix = self.tr("manifest found") if record.manifest_present else self.tr("no manifest")
            self.legacy_list.addItem(f"{record.name} — {suffix}\n{record.path}")

    def export_legacy_inventory(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Export legacy extension inventory"),
            "loofi-legacy-extensions.json",
            self.tr("JSON Files (*.json)"),
        )
        if path:
            LegacyExtensionService.export_manifest(Path(path))
            QMessageBox.information(self, self.tr("Inventory exported"), self.tr("No extension code or credential content was copied."))
