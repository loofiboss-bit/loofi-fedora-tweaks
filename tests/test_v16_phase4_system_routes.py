"""System-route presentation contracts for v16 Phase 4."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication, QStackedWidget, QTabWidget

from core.navigation import resolve
from ui.components import PageScaffold
from ui.diagnostics_tab import DiagnosticsTab, _BootSubTab
from ui.monitor_tab import MonitorTab
from ui.snapshot_tab import SnapshotTab
from ui.storage_tab import StorageTab


class TestPhase4SystemRouteStacks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    @patch("ui.monitor_tab.PerformanceCollector")
    def test_monitor_uses_shell_routes_instead_of_outer_tabs(self, _collector):
        tab = MonitorTab()
        self.addCleanup(tab.deleteLater)

        self.assertIsInstance(tab.pages, QStackedWidget)
        self.assertEqual(tab.findChildren(QTabWidget), [])
        self.assertEqual(len(tab.findChildren(PageScaffold)), 2)

        self.assertTrue(tab.activate_route(resolve("system-monitor:processes")))
        self.assertIs(tab.pages.currentWidget(), tab._processes_tab)
        self.assertTrue(tab.activate_route(resolve("monitor")))
        self.assertIs(tab.pages.currentWidget(), tab._performance_tab)

    @patch.object(_BootSubTab, "refresh_all")
    def test_diagnostics_keeps_canonical_troubleshoot_and_stable_subroutes(self, _refresh):
        tab = DiagnosticsTab()
        self.addCleanup(tab.deleteLater)

        self.assertIsInstance(tab.pages, QStackedWidget)
        self.assertEqual(len(tab.findChildren(PageScaffold)), 3)
        self.assertEqual(len(tab.findChildren(QTabWidget)), 1)

        self.assertTrue(tab.activate_route(resolve("diagnostics:boot")))
        self.assertEqual(tab.pages.currentIndex(), 2)
        self.assertTrue(tab.activate_route(resolve("diagnostics:watchtower")))
        self.assertEqual(tab.pages.currentIndex(), 1)
        self.assertTrue(tab.activate_route(resolve("diagnostics")))
        self.assertEqual(tab.pages.currentIndex(), 0)

    @patch("ui.storage_tab.QTimer.singleShot")
    def test_storage_uses_one_page_scaffold_without_legacy_header(self, _single_shot):
        tab = StorageTab()
        self.addCleanup(tab.deleteLater)

        self.assertEqual(len(tab.findChildren(PageScaffold)), 1)
        self.assertEqual(
            [label for label in tab.findChildren(type(tab.lbl_smart_model)) if label.objectName() == "header"],
            [],
        )

    @patch("ui.snapshot_tab.QTimer.singleShot")
    def test_recovery_uses_one_page_scaffold_without_legacy_header(self, _single_shot):
        tab = SnapshotTab()
        self.addCleanup(tab.deleteLater)

        self.assertEqual(len(tab.findChildren(PageScaffold)), 1)
        self.assertIsNone(tab.findChild(type(tab.backend_labels[0][1]), "snapHeader"))

    def test_hardware_system_check_and_maintenance_use_page_scaffolds(self):
        root = Path(__file__).resolve().parents[1] / "loofi-fedora-tweaks" / "ui"
        hardware = (root / "hardware_tab.py").read_text(encoding="utf-8")
        maintenance = (root / "maintenance_tab.py").read_text(encoding="utf-8")
        maintenance_action_center = (root / "maintenance_action_center.py").read_text(encoding="utf-8")
        system_check = (root / "system_check_tab.py").read_text(encoding="utf-8")

        self.assertIn("self.scaffold = PageScaffold(", hardware)
        self.assertNotIn('header = QLabel(self.tr("Hardware Control"))', hardware)
        self.assertIn("self.tabs = QStackedWidget()", maintenance)
        self.assertIn("self.scaffold = PageScaffold(", system_check)
        self.assertNotIn("Health History", maintenance_action_center)
        self.assertNotIn('header = QLabel(self.tr("My Fedora Today"))', maintenance)


if __name__ == "__main__":
    unittest.main()
