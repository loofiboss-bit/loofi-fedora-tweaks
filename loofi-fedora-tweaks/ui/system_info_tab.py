"""Responsive System Information presentation for the v16 System destination."""

from __future__ import annotations

import os

from core.export import ReportExporter
from core.plugins.interface import PluginInterface
from core.plugins.metadata import PluginMetadata
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QComboBox, QFileDialog, QLabel, QVBoxLayout, QWidget
from utils import system_info_utils
from utils.log import get_logger

from ui.components import DefinitionList, PageScaffold, SecondaryButton
from ui.components.layout import AdaptiveGrid

logger = get_logger(__name__)


class SystemInfoTab(QWidget, PluginInterface):
    """System facts grouped into compact, copyable responsive property cards."""

    _METADATA = PluginMetadata(
        id="system_info",
        name="System Info",
        description="Detailed system information including hardware specs, kernel, and uptime.",
        category="System",
        icon="info",
        badge="recommended",
        order=20,
    )

    def metadata(self) -> PluginMetadata:
        return self._METADATA

    def create_widget(self) -> QWidget:
        return self

    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.scaffold = PageScaffold(
            self.tr("System Information"),
            self.tr("Operating system, hardware, and current-state details."),
        )
        root.addWidget(self.scaffold)

        self.fact_grid = AdaptiveGrid(
            min_column_width=300,
            column_breakpoints=((0, 1), (760, 2), (1040, 3)),
        )
        self.fact_grid.setObjectName("systemInfoFactGrid")
        self.labels: dict[str, QLabel] = {}
        self.definition_rows = {}
        self._add_fact_group(
            self.tr("Operating system"),
            (
                (self.tr("Hostname"), "hostname"),
                (self.tr("Fedora version"), "fedora"),
                (self.tr("Kernel"), "kernel"),
            ),
        )
        self._add_fact_group(
            self.tr("Hardware"),
            (
                (self.tr("CPU"), "cpu"),
                (self.tr("RAM"), "ram"),
                (self.tr("Battery"), "battery"),
            ),
        )
        self._add_fact_group(
            self.tr("Current state"),
            (
                (self.tr("Disk usage (/)"), "disk"),
                (self.tr("Uptime"), "uptime"),
            ),
        )
        self.scaffold.add_widget(self.fact_grid)

        self.export_format_label = QLabel(self.tr("Format"), self)
        self.export_format_label.setAccessibleName(self.tr("Export format label"))
        self.export_format = QComboBox(self)
        self.export_format.addItems([self.tr("Markdown"), self.tr("HTML")])
        self.export_format.setAccessibleName(self.tr("Export format"))
        self.export_button = SecondaryButton(
            self.tr("Export Report"),
            description=self.tr("Export the current system report"),
            parent=self,
        )
        self.export_button.setAccessibleName(self.tr("Export system report"))
        self.export_button.clicked.connect(self._export_report)

        self._info_loaded = False

    def _add_fact_group(self, title: str, fields: tuple[tuple[str, str], ...]) -> None:
        card = DefinitionList(title)
        card.setProperty("systemInfoGroup", True)
        for label, key in fields:
            row = card.add_row(
                label,
                self.tr("Loading…"),
                copyable=True,
                description=self.tr("Copy this value when needed for support."),
            )
            row.copyRequested.connect(self._copy_value)
            row.copy_button.setEnabled(False)
            self.labels[key] = row.value
            self.definition_rows[key] = row
        self.fact_grid.add_card(card)

    def page_header_actions(self, route) -> tuple[object, ...]:
        """Expose only the existing format/export controls to the shell header."""
        if str(getattr(route, "id", "")) != "system_info":
            return ()
        return (
            self.export_format_label,
            self.export_format,
            (self.export_button, True),
        )

    def on_activate(self) -> None:
        """Defer system probes until the route is explicitly activated."""
        if self._info_loaded:
            return
        self._info_loaded = True
        QTimer.singleShot(0, self.refresh_info)

    def refresh_info(self) -> None:
        getters = (
            ("hostname", system_info_utils.get_hostname),
            ("kernel", system_info_utils.get_kernel_version),
            ("fedora", system_info_utils.get_fedora_release),
            ("cpu", system_info_utils.get_cpu_model),
            ("ram", system_info_utils.get_ram_usage),
            ("disk", system_info_utils.get_disk_usage),
            ("uptime", system_info_utils.get_uptime),
            ("battery", system_info_utils.get_battery_status),
        )
        for key, getter in getters:
            row = self.definition_rows[key]
            try:
                value = getter()
                if key == "battery" and value is None:
                    value = self.tr("No battery detected")
                row.set_value(str(value))
                row.copy_button.setEnabled(True)
            except (RuntimeError, OSError, ValueError, TypeError) as exc:
                logger.debug("Failed to refresh system info field %s: %s", key, exc)
                row.set_value(self.tr("Unavailable"))
                row.copy_button.setEnabled(False)

    @staticmethod
    def _copy_value(value: str) -> None:
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(value)

    def _export_report(self) -> None:
        """Export system report as Markdown or HTML."""
        fmt = "html" if self.export_format.currentText() == self.tr("HTML") else "markdown"
        ext = ".html" if fmt == "html" else ".md"
        default_name = f"system-report{ext}"

        path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Save System Report"),
            os.path.expanduser(f"~/Documents/{default_name}"),
            self.tr("HTML files (*.html);;Markdown files (*.md);;All files (*)"),
        )
        if path:
            try:
                ReportExporter.save_report(path, fmt)
            except (RuntimeError, OSError, ValueError, TypeError) as exc:
                logger.debug("Failed to export system report: %s", exc)
