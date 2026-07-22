"""
Backup Tab — Guided system backup wizard.
Part of v37.0.0 "Pinnacle" — T9.

Multi-step wizard flow using QStackedWidget:
Step 1: Detect backup tool
Step 2: Configure snapshot
Step 3: Create snapshot
Step 4: View results + existing snapshots
"""

import logging

from core.plugins.metadata import PluginMetadata
from core.product_catalog import plugin_metadata_for_module
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)
from utils.install_hints import build_install_hint

from ui.base_tab import BaseTab
from ui.components import ActionBar, InlineNotice, PageScaffold
from ui.shared_states import ResultBanner

logger = logging.getLogger(__name__)

# Kept for downstream imports; PageScaffold now owns visible page spacing.
CONTENT_MARGINS = (0, 0, 0, 0)


class BackupTab(BaseTab):
    """System backup wizard with step-by-step flow."""

    _METADATA = plugin_metadata_for_module(__name__)

    actionCenterRequested = pyqtSignal(str, object)

    def metadata(self) -> PluginMetadata:
        return self._METADATA

    def create_widget(self) -> QWidget:
        return self

    def __init__(self):
        super().__init__()
        self._loaded = False
        self.init_ui()

    def init_ui(self):
        """Build the backup wizard UI."""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scaffold = PageScaffold(
            self.tr("Backups"),
            self.tr("Create and restore backup snapshots separately from Loofi recovery points."),
        )
        root.addWidget(self.scaffold)
        layout = self.scaffold.content_layout

        self.scope_notice = InlineNotice(
            self.tr("Backups and recovery points are separate"),
            self.tr("This page manages Timeshift, Snapper, and Btrfs backups. Loofi recovery points remain under System."),
            kind="info",
        )
        layout.addWidget(self.scope_notice)

        # --- Wizard Stack ---
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        # Page 0: Detection
        self.stack.addWidget(self._create_detect_page())
        # Page 1: Configure
        self.stack.addWidget(self._create_configure_page())
        # Page 2: Snapshot list + manage
        self.stack.addWidget(self._create_manage_page())

        # --- Navigation ---
        nav = ActionBar()
        self.back_btn = QPushButton(self.tr("Back"))
        self.back_btn.clicked.connect(self._go_back)
        self.back_btn.setEnabled(False)
        nav.add_action(self.back_btn)

        self.next_btn = QPushButton(self.tr("Next"))
        self.next_btn.clicked.connect(self._go_next)
        nav.add_action(self.next_btn, primary=True)
        layout.addWidget(nav)

        # --- Output ---
        self.add_output_disclosure(layout, self.tr("Show backup command output"))

    @staticmethod
    def activate_route(route) -> bool:
        """Accept the stable Backup route without introducing sub-navigation."""
        return str(getattr(route, "id", route)) == "backup"

    # ================================================================
    # PAGES
    # ================================================================

    def _create_detect_page(self) -> QWidget:
        """Page 0: Detect available backup tools."""
        page = QWidget()
        layout = QVBoxLayout(page)

        info = QLabel(
            self.tr(
                "This wizard helps you create and manage system snapshots.\n"
                "These recovery points protect system state through Timeshift or Snapper; "
                "they are not a backup of your personal files."
            )
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # Tool status
        self.tool_result = ResultBanner(
            self.tr("Backup tool status"),
            self.tr("Detect Timeshift or Snapper before creating a recovery point."),
        )
        self.tool_status = self.tool_result.message_label
        self.tool_status.setObjectName("toolStatus")
        layout.addWidget(self.tool_result)

        self.detect_btn = QPushButton(self.tr("Detect Backup Tools"))
        self.detect_btn.clicked.connect(self._detect_tools)
        layout.addWidget(self.detect_btn)

        layout.addStretch()
        return page

    def _create_configure_page(self) -> QWidget:
        """Page 1: Configure snapshot creation."""
        page = QWidget()
        layout = QVBoxLayout(page)

        group = QGroupBox(self.tr("Create Snapshot"))
        group_layout = QVBoxLayout(group)

        desc_row = QHBoxLayout()
        desc_row.addWidget(QLabel(self.tr("Description:")))
        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText(self.tr("Loofi backup"))
        self.desc_input.setText("Loofi backup")
        desc_row.addWidget(self.desc_input)
        group_layout.addLayout(desc_row)

        self.tool_info = QLabel()
        group_layout.addWidget(self.tool_info)

        self.create_btn = QPushButton(self.tr("Create Snapshot"))
        self.create_btn.clicked.connect(self._create_snapshot)
        group_layout.addWidget(self.create_btn)

        layout.addWidget(group)
        layout.addStretch()
        return page

    def _create_manage_page(self) -> QWidget:
        """Page 2: List and manage existing snapshots."""
        page = QWidget()
        layout = QVBoxLayout(page)

        header = QHBoxLayout()
        header.addWidget(QLabel(self.tr("Existing Snapshots")))
        header.addStretch()

        refresh_btn = QPushButton(self.tr("Refresh"))
        refresh_btn.clicked.connect(self._load_snapshots)
        header.addWidget(refresh_btn)
        layout.addLayout(header)

        # Snapshot table
        self.snap_table = QTableWidget(0, 4)
        self.snap_table.setHorizontalHeaderLabels(
            [
                self.tr("ID"),
                self.tr("Date"),
                self.tr("Description"),
                self.tr("Tool"),
            ]
        )
        h_header = self.snap_table.horizontalHeader()
        assert h_header is not None
        h_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        h_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.snap_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.snap_table.setProperty("maxVisibleRows", 4)
        BaseTab.configure_table(self.snap_table)
        layout.addWidget(self.snap_table)

        # Action buttons
        actions = QHBoxLayout()
        self.restore_btn = QPushButton(self.tr("Manual High-Risk Restore"))
        self.restore_btn.clicked.connect(self._restore_selected)
        actions.addWidget(self.restore_btn)

        self.delete_btn = QPushButton(self.tr("Manual Irreversible Delete"))
        self.delete_btn.clicked.connect(self._delete_selected)
        actions.addWidget(self.delete_btn)

        actions.addStretch()
        layout.addLayout(actions)

        return page

    # ================================================================
    # NAVIGATION
    # ================================================================

    def _go_back(self):
        """Go to previous wizard page."""
        idx = self.stack.currentIndex()
        if idx > 0:
            self.stack.setCurrentIndex(idx - 1)
        self.back_btn.setEnabled(self.stack.currentIndex() > 0)
        self.next_btn.setText(
            self.tr("Finish")
            if self.stack.currentIndex() == self.stack.count() - 1
            else self.tr("Next")
        )

    def _go_next(self):
        """Go to next wizard page."""
        idx = self.stack.currentIndex()
        if idx < self.stack.count() - 1:
            self.stack.setCurrentIndex(idx + 1)
            if idx == 0:
                self._setup_configure_page()
            if idx + 1 == 2:
                self._load_snapshots()
        self.back_btn.setEnabled(self.stack.currentIndex() > 0)
        self.next_btn.setText(
            self.tr("Finish")
            if self.stack.currentIndex() == self.stack.count() - 1
            else self.tr("Next")
        )

    def showEvent(self, event):
        """Auto-detect on first show."""
        super().showEvent(event)
        if not self._loaded:
            self._detect_tools()
            self._loaded = True

    # ================================================================
    # ACTIONS
    # ================================================================

    def _detect_tools(self):
        """Detect available backup tools."""
        try:
            from utils.backup_wizard import BackupWizard

            tool = BackupWizard.detect_backup_tool()
            available = BackupWizard.get_available_tools()

            if tool == "none":
                install_timeshift = build_install_hint("timeshift")
                install_snapper = build_install_hint("snapper")
                message = self.tr(
                    "No backup tool found.\n"
                    "Install timeshift or snapper:\n"
                    "  {timeshift}\n"
                    "  {snapper}"
                ).format(
                    timeshift=install_timeshift,
                    snapper=install_snapper,
                )
                self.tool_result.set_result(
                    "warning", self.tr("Backup tool unavailable"), message
                )
                self.next_btn.setEnabled(False)
            else:
                tools_str = ", ".join(available)
                message = self.tr("Backup tool detected: {}\nAvailable tools: {}").format(
                    tool, tools_str
                )
                self.tool_result.set_result(
                    "success", self.tr("Backup tool ready"), message
                )
                self.next_btn.setEnabled(True)
                self._detected_tool = tool

            self.append_output(self.tr("Tool detection complete: {}\n").format(tool))
        except (RuntimeError, OSError, ValueError) as e:
            logger.error("Tool detection failed: %s", e)
            self.tool_result.set_result(
                "error",
                self.tr("Backup tool detection failed"),
                self.tr("Detection failed: {}").format(e),
            )

    def _setup_configure_page(self):
        """Prepare configure page with detected tool info."""
        tool = getattr(self, "_detected_tool", "none")
        self.tool_info.setText(self.tr("Using backup tool: {}").format(tool))

    def _create_snapshot(self):
        """Hand recovery-point creation to Action Center."""
        tool = str(getattr(self, "_detected_tool", "") or "")
        if tool not in {"timeshift", "snapper"}:
            self.append_output(self.tr("Only Timeshift and Snapper creation can be verified.\n"))
            return
        desc = self.desc_input.text().strip() or "Loofi backup"
        self.actionCenterRequested.emit(
            "create-recovery-point",
            {"backend": tool, "description": desc},
        )

    def _load_snapshots(self):
        """Load existing snapshots into the table."""
        try:
            from utils.backup_wizard import BackupWizard

            tool = getattr(self, "_detected_tool", None)
            snapshots = BackupWizard.list_snapshots(tool=tool)
            self.snap_table.setRowCount(len(snapshots))

            for row, snap in enumerate(snapshots):
                self.snap_table.setItem(row, 0, BaseTab.make_table_item(snap.id))
                self.snap_table.setItem(row, 1, BaseTab.make_table_item(snap.date))
                self.snap_table.setItem(
                    row, 2, BaseTab.make_table_item(snap.description)
                )
                self.snap_table.setItem(row, 3, BaseTab.make_table_item(snap.tool))

            if not snapshots:
                BaseTab.set_table_empty_state(
                    self.snap_table, self.tr("No snapshots found")
                )
            else:
                normalize = getattr(BaseTab, "ensure_table_row_heights", None)
                if callable(normalize):
                    normalize(self.snap_table)

            self.append_output(self.tr("Found {} snapshots.\n").format(len(snapshots)))
        except (RuntimeError, OSError, ValueError) as e:
            logger.error("Failed to load snapshots: %s", e)
            self.append_output(f"[ERROR] {e}\n")

    def _restore_selected(self):
        """Restore selected snapshot."""
        row = self.snap_table.currentRow()
        if row < 0:
            self.append_output(self.tr("Select a snapshot to restore.\n"))
            return

        snap_id = self.snap_table.item(row, 0)
        if not snap_id:
            return

        self.actionCenterRequested.emit("restore-recovery-point", {})
        self.append_output(self.tr("Review recovery-point restore guidance in Action Center.\n"))

    def _delete_selected(self):
        """Delete selected snapshot."""
        row = self.snap_table.currentRow()
        if row < 0:
            self.append_output(self.tr("Select a snapshot to delete.\n"))
            return

        snap_id = self.snap_table.item(row, 0)
        if not snap_id:
            return

        self.actionCenterRequested.emit("delete-recovery-point", {})
        self.append_output(self.tr("Review destructive recovery-point deletion guidance in Action Center.\n"))
