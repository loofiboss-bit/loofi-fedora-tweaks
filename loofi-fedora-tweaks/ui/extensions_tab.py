"""
Desktop shell extension management.

Provides a UI for browsing, installing, enabling, disabling, and
removing GNOME Shell and KDE Plasma extensions.
"""

import logging

from core.plugins.metadata import PluginMetadata
from core.product_catalog import plugin_metadata_for_module
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from ui.base_tab import BaseTab
from ui.components import PageScaffold
from ui.design import semantic_color

logger = logging.getLogger(__name__)


class ExtensionsTab(BaseTab):
    """Desktop shell extension manager — GNOME and KDE."""

    _METADATA = plugin_metadata_for_module(__name__)
    actionCenterRequested = pyqtSignal(str, object)

    def metadata(self) -> PluginMetadata:
        return self._METADATA

    def create_widget(self) -> QWidget:
        return self

    def __init__(self):
        super().__init__()
        self._extensions_loaded = False
        self.init_ui()

    def init_ui(self):
        """Build the extensions management UI."""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scaffold = PageScaffold(
            self.tr("Desktop extensions"),
            self.tr("Browse and manage supported desktop-shell extensions."),
        )
        root.addWidget(self.scaffold)
        layout = self.scaffold.content_layout

        header = QHBoxLayout()
        header.addStretch()

        self.de_label = QLabel()
        self.de_label.setObjectName("deLabel")
        header.addWidget(self.de_label)
        layout.addLayout(header)

        # --- Search + Filter ---
        filter_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(self.tr("Search extensions..."))
        self.search_input.textChanged.connect(self._filter_table)
        filter_row.addWidget(self.search_input)

        self.status_filter = QComboBox()
        self.status_filter.addItems(
            [
                self.tr("All"),
                self.tr("Enabled"),
                self.tr("Disabled"),
            ]
        )
        self.status_filter.currentIndexChanged.connect(self._filter_table)
        filter_row.addWidget(self.status_filter)

        self.refresh_btn = QPushButton(self.tr("Refresh"))
        self.refresh_btn.clicked.connect(self._load_extensions)
        filter_row.addWidget(self.refresh_btn)

        layout.addLayout(filter_row)

        # --- Extensions Table ---
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            [
                self.tr("Extension"),
                self.tr("Status"),
                self.tr("Desktop"),
                self.tr("Actions"),
            ]
        )
        h_header = self.table.horizontalHeader()
        assert h_header is not None
        h_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        h_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setProperty("maxVisibleRows", 4)
        BaseTab.configure_table(self.table)
        layout.addWidget(self.table)

        # --- Action Buttons ---
        actions = QHBoxLayout()
        self.install_btn = QPushButton(self.tr("Install Extension"))
        self.install_btn.clicked.connect(self._install_extension)
        actions.addWidget(self.install_btn)

        self.remove_btn = QPushButton(self.tr("Remove Selected"))
        self.remove_btn.clicked.connect(self._remove_selected)
        actions.addWidget(self.remove_btn)

        actions.addStretch()
        layout.addLayout(actions)

        self.add_output_disclosure(layout, self.tr("Show extension operation output"))

        # Detect desktop and load
        self._detect_desktop()

    def showEvent(self, event):
        """Load extensions on first show."""
        super().showEvent(event)
        if not self._extensions_loaded:
            self._load_extensions()
            self._extensions_loaded = True

    def _detect_desktop(self):
        """Detect and display current desktop environment."""
        try:
            from utils.extension_manager import ExtensionManager

            de = ExtensionManager.detect_desktop()
            labels = {"gnome": "GNOME Shell", "kde": "KDE Plasma", "unknown": "Unknown"}
            self.de_label.setText(
                self.tr("Desktop: {}").format(labels.get(de.value, de.value))
            )

            if not ExtensionManager.is_supported():
                self.install_btn.setEnabled(False)
                self.remove_btn.setEnabled(False)
                self.append_output(
                    self.tr("Extension management not supported on this desktop.\n")
                )
        except (RuntimeError, OSError, ValueError) as e:
            logger.warning("Desktop detection failed: %s", e)
            self.de_label.setText(self.tr("Desktop: Unknown"))

    def _load_extensions(self):
        """Load installed extensions into the table."""
        try:
            from utils.extension_manager import ExtensionManager

            extensions = ExtensionManager.list_installed()
            self.table.setRowCount(len(extensions))

            for row, ext in enumerate(extensions):
                # Name
                self.table.setItem(
                    row, 0, BaseTab.make_table_item(ext.name or ext.uuid)
                )
                # Status
                status = self.tr("Enabled") if ext.enabled else self.tr("Disabled")
                color = semantic_color("success" if ext.enabled else "warning")
                self.table.setItem(row, 1, BaseTab.make_table_item(status, color=color))
                # Desktop
                self.table.setItem(row, 2, BaseTab.make_table_item(ext.desktop.upper()))
                # Action buttons
                action_widget = self._create_action_buttons(ext)
                self.table.setCellWidget(row, 3, action_widget)

            if not extensions:
                BaseTab.set_table_empty_state(
                    self.table, self.tr("No extensions found")
                )
            else:
                normalize = getattr(BaseTab, "ensure_table_row_heights", None)
                if callable(normalize):
                    normalize(self.table)

            self.append_output(
                self.tr("Loaded {} extensions.\n").format(len(extensions))
            )
        except (RuntimeError, OSError, ValueError) as e:
            logger.error("Failed to load extensions: %s", e)
            self.append_output(
                self.tr("[ERROR] Failed to load extensions: {}\n").format(e)
            )

    def _create_action_buttons(self, ext) -> QWidget:
        """Create enable/disable toggle button for an extension row."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(2, 2, 2, 2)

        if ext.enabled:
            btn = QPushButton(self.tr("Disable"))
            btn.clicked.connect(
                lambda checked, u=ext.uuid: self._toggle_extension(u, False)
            )
        else:
            btn = QPushButton(self.tr("Enable"))
            btn.clicked.connect(
                lambda checked, u=ext.uuid: self._toggle_extension(u, True)
            )

        layout.addWidget(btn)
        return widget

    def _toggle_extension(self, uuid: str, enable: bool):
        """Enable or disable an extension."""
        action_id = "enable-desktop-extension" if enable else "disable-desktop-extension"
        self.actionCenterRequested.emit(action_id, {})

    def _install_extension(self):
        """Install an extension by UUID from search input."""
        uuid = self.search_input.text().strip()
        if not uuid:
            self.append_output(self.tr("Enter an extension UUID to install.\n"))
            return
        self.actionCenterRequested.emit("install-desktop-extension", {})

    def _remove_selected(self):
        """Remove selected extension."""
        row = self.table.currentRow()
        if row < 0:
            self.append_output(self.tr("Select an extension to remove.\n"))
            return
        name_item = self.table.item(row, 0)
        if not name_item:
            return
        self.actionCenterRequested.emit("remove-desktop-extension", {})

    def _filter_table(self):
        """Filter table rows by search text and status."""
        query = self.search_input.text().lower()
        status_idx = self.status_filter.currentIndex()

        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 0)
            status_item = self.table.item(row, 1)
            if not name_item:
                continue

            name_match = query in name_item.text().lower()
            status_match = True
            if status_idx == 1 and status_item:
                status_match = "enabled" in status_item.text().lower()
            elif status_idx == 2 and status_item:
                status_match = "disabled" in status_item.text().lower()

            self.table.setRowHidden(row, not (name_match and status_match))
