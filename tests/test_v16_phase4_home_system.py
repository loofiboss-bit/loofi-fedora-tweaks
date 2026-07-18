"""Focused acceptance tests for v16 Phase 4 Home and System Information."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication, QComboBox, QGroupBox, QPushButton

from core.navigation import resolve
from ui.components import DefinitionList, DefinitionRow, PageHeader, PageScaffold
from ui.main_window import MainWindow
from ui.system_info_tab import SystemInfoTab


class TestPhase4SystemInformation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def tearDown(self):
        tab = getattr(self, "tab", None)
        if tab is not None:
            tab.deleteLater()

    def _build(self) -> SystemInfoTab:
        self.tab = SystemInfoTab()
        return self.tab

    @patch("ui.system_info_tab.system_info_utils.get_hostname")
    def test_constructor_is_probe_free_and_uses_three_property_groups(self, hostname):
        tab = self._build()

        hostname.assert_not_called()
        self.assertEqual(len(tab.findChildren(PageScaffold)), 1)
        self.assertEqual(len(tab.findChildren(DefinitionList)), 3)
        self.assertEqual(len(tab.findChildren(DefinitionRow)), 8)
        self.assertEqual(tab.findChildren(QGroupBox), [])
        self.assertEqual(
            [group.title_label.text() for group in tab.findChildren(DefinitionList)],
            ["Operating system", "Hardware", "Current state"],
        )
        self.assertTrue(all(not row.copy_button.isEnabled() for row in tab.definition_rows.values()))

    def test_fact_grid_has_explicit_one_two_three_column_breakpoints(self):
        tab = self._build()

        tab.fact_grid._reflow(740)
        self.assertEqual(tab.fact_grid._columns, 1)
        tab.fact_grid._reflow(800)
        self.assertEqual(tab.fact_grid._columns, 2)
        tab.fact_grid._reflow(1080)
        self.assertEqual(tab.fact_grid._columns, 3)
        self.assertEqual(tab.scaffold.content.maximumWidth(), 1120)

    @patch("ui.system_info_tab.QTimer.singleShot")
    def test_activation_schedules_existing_probes_only_once(self, single_shot):
        tab = self._build()

        tab.on_activate()
        tab.on_activate()

        single_shot.assert_called_once_with(0, tab.refresh_info)

    @patch("ui.system_info_tab.system_info_utils.get_battery_status", return_value=None)
    @patch("ui.system_info_tab.system_info_utils.get_uptime", return_value="2 hours")
    @patch("ui.system_info_tab.system_info_utils.get_disk_usage", return_value="42%")
    @patch("ui.system_info_tab.system_info_utils.get_ram_usage", return_value="4 / 16 GiB")
    @patch("ui.system_info_tab.system_info_utils.get_cpu_model", return_value="Test CPU")
    @patch("ui.system_info_tab.system_info_utils.get_fedora_release", return_value="Fedora 44")
    @patch("ui.system_info_tab.system_info_utils.get_kernel_version", return_value="6.15")
    @patch("ui.system_info_tab.system_info_utils.get_hostname", side_effect=OSError("unavailable"))
    def test_probe_failures_are_isolated_per_copyable_row(self, *_mocks):
        tab = self._build()

        tab.refresh_info()

        self.assertEqual(tab.definition_rows["hostname"].value.text(), "Unavailable")
        self.assertFalse(tab.definition_rows["hostname"].copy_button.isEnabled())
        self.assertEqual(tab.definition_rows["kernel"].value.text(), "6.15")
        self.assertTrue(tab.definition_rows["kernel"].copy_button.isEnabled())
        self.assertEqual(tab.definition_rows["battery"].value.text(), "No battery detected")

    def test_copy_action_uses_the_current_property_value(self):
        tab = self._build()
        row = tab.definition_rows["kernel"]
        row.set_value("6.15.8-300.fc44")
        row.copy_button.setEnabled(True)

        row.copy_button.click()

        self.assertEqual(QApplication.clipboard().text(), "6.15.8-300.fc44")

    def test_export_controls_follow_shell_header_lifecycle_without_duplicates(self):
        tab = self._build()
        header = PageHeader()
        entry = SimpleNamespace(page_widget=tab)
        window = SimpleNamespace(
            _breadcrumb_frame=header,
            _sidebar_index={"system_info": entry},
            _real_widget_for_entry=lambda current: current.page_widget,
        )
        route = resolve("system_info")
        self.assertIsNotNone(route)

        MainWindow._sync_page_header_actions(window, route)
        self.assertEqual(len(header.action_bar.findChildren(QComboBox)), 1)
        buttons = header.action_bar.findChildren(QPushButton)
        self.assertEqual([button.text() for button in buttons], ["Export Report"])
        self.assertNotIn("Refresh", {button.text() for button in buttons})
        self.assertNotIn("Copy Summary", {button.text() for button in buttons})

        MainWindow._sync_page_header_actions(window, None)
        self.assertEqual(header.action_bar.findChildren(QComboBox), [])
        self.assertIs(tab.export_button.parentWidget(), tab)

        MainWindow._sync_page_header_actions(window, route)
        self.assertEqual(len(header.action_bar.findChildren(QComboBox)), 1)
        self.assertEqual(len(header.action_bar.findChildren(QPushButton)), 1)

    @patch("ui.system_info_tab.ReportExporter.save_report")
    @patch("ui.system_info_tab.QFileDialog.getSaveFileName", return_value=("/tmp/system-report.html", ""))
    def test_existing_export_behavior_preserves_html_format(self, _dialog, save_report):
        tab = self._build()
        tab.export_format.setCurrentText("HTML")

        tab._export_report()

        save_report.assert_called_once_with("/tmp/system-report.html", "html")


if __name__ == "__main__":
    unittest.main()
