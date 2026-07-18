"""Focused acceptance tests for v16 Phase 5 Standard destinations."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication, QStackedWidget

from core.navigation import resolve
from core.navigation.models import NavigationMode
from ui.components import DetailsDisclosure, InlineNotice, PageScaffold


ROOT = Path(__file__).resolve().parents[1]
STANDARD_MODULES = (
    "software_tab.py",
    "maintenance_tab.py",
    "network_tab.py",
    "security_tab.py",
    "backup_tab.py",
    "desktop_tab.py",
    "settings_tab.py",
)


class TestPhase5SourceContract(unittest.TestCase):
    def test_standard_destinations_do_not_own_application_tab_bars(self):
        for filename in STANDARD_MODULES:
            source = (ROOT / "loofi-fedora-tweaks" / "ui" / filename).read_text(
                encoding="utf-8"
            )
            self.assertNotIn("QTabWidget", source, filename)

    def test_standard_destinations_use_shared_page_scaffolds(self):
        for filename in STANDARD_MODULES:
            source = (ROOT / "loofi-fedora-tweaks" / "ui" / filename).read_text(
                encoding="utf-8"
            )
            self.assertIn("PageScaffold", source, filename)

    def test_shell_owned_titles_are_not_repeated_by_standard_pages(self):
        legacy_header_markers = (
            'setObjectName("header")',
            'setObjectName("settingsHeader")',
            'setObjectName("sectionTitle")',
        )
        for filename in STANDARD_MODULES:
            source = (ROOT / "loofi-fedora-tweaks" / "ui" / filename).read_text(
                encoding="utf-8"
            )
            for marker in legacy_header_markers:
                self.assertNotIn(marker, source, filename)

    def test_visual_evidence_manifest_is_complete_and_current(self):
        manifest_path = ROOT / "docs" / "reports" / "V16_PHASE5_SCREENSHOTS.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest["phase"], 5)
        self.assertEqual(len(manifest["captures"]), 8)
        self.assertEqual(
            {tuple(item["viewport"]) for item in manifest["captures"]},
            {(860, 720), (1918, 1018)},
        )
        self.assertEqual(
            {item["destination"] for item in manifest["captures"]},
            {"software-updates", "network-security", "desktop", "settings"},
        )
        for item in manifest["captures"]:
            image_path = ROOT / item["path"]
            self.assertTrue(image_path.is_file(), image_path)
            self.assertEqual(
                hashlib.sha256(image_path.read_bytes()).hexdigest(),
                item["sha256"],
            )
            self.assertEqual(item["captured_dimensions"], item["viewport"])

    def test_capture_harness_uses_the_real_guarded_main_window(self):
        source = (ROOT / "scripts" / "capture_v16_phase5.py").read_text(
            encoding="utf-8"
        )
        for marker in (
            "MainWindow()",
            "isolated_capture_home()",
            "guarded_subprocesses()",
            'patch.object(CommandRunner, "run_command", reject_command)',
            'window.apply_navigation_mode(NavigationMode.STANDARD)',
        ):
            self.assertIn(marker, source)


class TestPhase5RoutePresentation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    @staticmethod
    def _assert_current_page_scaffolded(stack: QStackedWidget) -> None:
        page = stack.currentWidget()
        assert page is not None
        if isinstance(page, PageScaffold):
            return
        if page.findChildren(PageScaffold):
            return
        widget = getattr(page, "widget", lambda: None)()
        if isinstance(widget, PageScaffold):
            return
        raise AssertionError("active route has no PageScaffold")

    def test_software_routes_use_one_shell_owned_stack(self):
        # test_software_tab intentionally replaces Qt modules while collecting,
        # so keep this cross-file acceptance assertion source-level and leave
        # widget behavior to that module's focused tests.
        source = (ROOT / "loofi-fedora-tweaks" / "ui" / "software_tab.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('self.tabs = QStackedWidget()', source)
        self.assertIn('"software:apps": 0', source)
        self.assertIn('"software:repos": 1', source)
        self.assertIn('"software:flatpak": 2', source)
        self.assertGreaterEqual(source.count("PageScaffold("), 3)

    @patch("ui.network_tab.QTimer.singleShot")
    def test_network_routes_use_scaffolded_pages(self, _single_shot):
        from ui.network_tab import NetworkTab

        tab = NetworkTab()
        self.addCleanup(tab.deleteLater)
        for route_id, index in (
            ("network:connections", 0),
            ("network:dns", 1),
            ("network:privacy", 2),
            ("network:monitoring", 3),
        ):
            self.assertTrue(tab.activate_route(resolve(route_id)))
            self.assertEqual(tab.tabs.currentIndex(), index)
            self._assert_current_page_scaffolded(tab.tabs)

    @patch("ui.security_tab.SandboxManager.is_bubblewrap_installed", return_value=False)
    @patch("ui.security_tab.SandboxManager.is_firejail_installed", return_value=False)
    @patch("ui.security_tab.USBGuardManager.is_installed", return_value=False)
    @patch("ui.security_tab.PortAuditor.scan_ports", return_value=[])
    @patch("ui.security_tab.PortAuditor.is_firewalld_running", return_value=True)
    @patch(
        "ui.security_tab.PortAuditor.get_security_score",
        return_value={
            "score": 90,
            "rating": "Good",
            "open_ports": 0,
            "risky_ports": 0,
            "recommendations": [],
        },
    )
    def test_security_routes_separate_state_changes_and_exposure(self, *_mocks):
        from ui.security_tab import SecurityTab

        tab = SecurityTab()
        self.addCleanup(tab.deleteLater)
        for route_id, index in (
            ("security:overview", 0),
            ("security:firewall", 1),
            ("security:privacy", 2),
            ("security:ports", 3),
        ):
            self.assertTrue(tab.activate_route(resolve(route_id)))
            self.assertEqual(tab.pages.currentIndex(), index)
            self._assert_current_page_scaffolded(tab.pages)
        self.assertIsInstance(tab.activity_details, DetailsDisclosure)
        self.assertFalse(tab.activity_details.details.isVisible())

    @patch("ui.desktop_tab.QTimer.singleShot")
    @patch("ui.desktop_tab.KWinManager.is_wayland", return_value=True)
    @patch("ui.desktop_tab.KWinManager.is_kde", return_value=True)
    def test_desktop_routes_use_scaffolded_pages(self, *_mocks):
        from ui.desktop_tab import DesktopTab

        tab = DesktopTab()
        self.addCleanup(tab.deleteLater)
        for route_id, index in (
            ("desktop:director", 0),
            ("desktop:theming", 1),
            ("desktop:display", 2),
        ):
            self.assertTrue(tab.activate_route(resolve(route_id)))
            self.assertEqual(tab.sub_tabs.currentIndex(), index)
            self._assert_current_page_scaffolded(tab.sub_tabs)

    @patch("utils.navigation_mode.NavigationModeManager.get_mode", return_value=NavigationMode.STANDARD)
    @patch("ui.settings_tab.SettingsManager.instance")
    def test_settings_routes_use_shell_navigation_not_internal_tabs(
        self,
        manager_instance,
        _get_mode,
    ):
        from ui.settings_tab import SettingsTab

        values = {
            "theme": "dark",
            "follow_system_theme": True,
            "start_minimized": False,
            "show_notifications": True,
            "confirm_dangerous_actions": True,
            "restore_last_tab": True,
            "log_level": "INFO",
            "check_updates_on_start": True,
        }
        manager = MagicMock()
        manager.get.side_effect = lambda key, default=None: values.get(key, default)
        manager_instance.return_value = manager
        tab = SettingsTab()
        self.addCleanup(tab.deleteLater)
        for route_id, index in (
            ("settings:appearance", 0),
            ("settings:behavior", 1),
            ("settings:advanced", 2),
            ("settings:repair", 3),
            ("settings:about", 4),
        ):
            self.assertTrue(tab.activate_route(resolve(route_id)))
            self.assertEqual(tab.settings_tabs.currentIndex(), index)
            self._assert_current_page_scaffolded(tab.settings_tabs)

    def test_backup_is_scaffolded_and_distinct_from_recovery_points(self):
        from ui.backup_tab import BackupTab

        tab = BackupTab()
        self.addCleanup(tab.deleteLater)
        self.assertTrue(tab.activate_route(SimpleNamespace(id="backup")))
        self.assertEqual(tab.layout().getContentsMargins(), (0, 0, 0, 0))
        self.assertEqual(len(tab.findChildren(PageScaffold)), 1)
        self.assertIsInstance(tab.scope_notice, InlineNotice)
        self.assertIn("recovery points", tab.scope_notice.message_label.text().lower())

    @patch("ui.maintenance_tab.SystemManager.get_package_manager", return_value="dnf")
    @patch("ui.maintenance_tab.SystemManager.is_atomic", return_value=False)
    def test_traditional_maintenance_routes_are_scaffolded(self, _atomic, _manager):
        from ui.maintenance_tab import MaintenanceTab

        tab = MaintenanceTab()
        self.addCleanup(tab.deleteLater)
        for route_id in (
            "maintenance:updates",
            "maintenance:action-center",
            "maintenance:cleanup",
            "maintenance:upgrade-assistant",
        ):
            self.assertTrue(tab.activate_route(resolve(route_id)))
            self._assert_current_page_scaffolded(tab.tabs)

    @patch("ui.maintenance_tab.SystemManager.get_variant_name", return_value="Kinoite")
    @patch("ui.maintenance_tab.SystemManager.get_package_manager", return_value="rpm-ostree")
    @patch("ui.maintenance_tab.SystemManager.is_atomic", return_value=True)
    def test_atomic_overlays_route_is_scaffolded(self, *_mocks):
        from ui.maintenance_tab import MaintenanceTab

        tab = MaintenanceTab()
        self.addCleanup(tab.deleteLater)
        self.assertTrue(tab.activate_route(resolve("maintenance:overlays")))
        self._assert_current_page_scaffolded(tab.tabs)


if __name__ == "__main__":
    unittest.main()
