"""Personal route integration and native launch reader ownership regressions."""
import time
import unittest
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PyQt6.QtWidgets import QApplication, QPushButton, QWidget

from core.catalog_models import CapabilityState, NativeHandoffId
from services.desktop.native_handoff import NativeHandoffLaunch
from services.software.source_status import DnfRepository, DnfSourceSnapshot, SoftwareSourceStatusService, SourceStatusReason
from ui.install_workflow import InstallWorkflowPage
from ui.lazy_widget import LazyWidget
from ui.main_window_utility import MainWindowUtilityMixin
from ui.native_handoff_card import ManagedNativeHandoffCard
from ui.update_workflow import UpdateWorkflowPage


class PersonalIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def pump_until(self, predicate):
        deadline = time.monotonic() + 3
        while not predicate() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.001)
        self.assertTrue(predicate())

    @patch("ui.operation_worker.OperationControllerQtAdapter.start", return_value=True)
    def test_apps_sources_and_badges_use_exact_observation_and_clear_failure(self, start):
        service = SoftwareSourceStatusService()
        page = InstallWorkflowPage(source_status_service=service)
        self.addCleanup(page.deleteLater)
        self.assertEqual(start.call_args.args[0], service.combined_snapshot)
        snapshot = DnfSourceSnapshot("now", (DnfRepository("rpmfusion-free", "Free", True),))
        page._apply_source_observation((snapshot, service.badges_from_sources(snapshot)))
        self.assertIs(page.sources_widget.snapshot, snapshot)
        self.assertIn("RPM Fusion Free: Enabled", page.dnf_source_status.text())
        page.focus_sources()
        self.assertEqual(page.view_filter.currentData(), "sources")
        self.assertFalse(page.sources_widget.isHidden())
        self.assertTrue(page.application_list.isHidden())
        self.assertTrue(page.review_card.isHidden())
        self.assertTrue(page.installed_card.isHidden())
        failed = DnfSourceSnapshot("later", reason=SourceStatusReason.TIMEOUT)
        page._apply_source_observation((failed, service.badges_from_sources(failed)))
        self.assertEqual(page.sources_widget.table.topLevelItemCount(), 0)
        self.assertIn("RPM Fusion Free: Unknown", page.dnf_source_status.text())

    @patch("ui.operation_worker.OperationControllerQtAdapter.start", return_value=True)
    def test_default_constructor_sources_refresh_is_reachable(self, start):
        page = InstallWorkflowPage()
        self.addCleanup(page.deleteLater)
        page.focus_sources()
        self.assertEqual(start.call_args.args[0], page.sources_widget.service.sources_snapshot)

    def test_updates_navigation_loads_apps_once_and_focuses_sources(self):
        page = QWidget()
        page.focus_sources = Mock()
        loader = Mock(return_value=page)
        lazy = LazyWidget(loader)
        self.addCleanup(lazy.deleteLater)
        owner = SimpleNamespace(_activate_destination=Mock(), _sidebar_index={"utility_install": SimpleNamespace(page_widget=lazy)})
        MainWindowUtilityMixin._open_package_sources(owner)
        MainWindowUtilityMixin._open_package_sources(owner)
        loader.assert_called_once()
        self.assertEqual(page.focus_sources.call_count, 2)
        owner._activate_destination.assert_called_with("install")
        updates = UpdateWorkflowPage()
        self.addCleanup(updates.deleteLater)
        requested = Mock()
        updates.sourcesRequested.connect(requested)
        updates.sources_button.click()
        requested.assert_called_once()

    @patch("ui.native_handoff_card.SystemManager.get_platform_profile", return_value=Mock())
    @patch("ui.native_handoff_card.QProcess.startDetached")
    def test_missing_native_module_preserves_unavailable_reason(self, launch, _profile):
        service = Mock()
        service.prepare_launch.return_value = None
        service.availability.return_value = SimpleNamespace(detail="Default Applications module is not installed.", state=CapabilityState.UNAVAILABLE)
        card = ManagedNativeHandoffCard(NativeHandoffId.DEFAULT_APPLICATIONS, title="Default apps", description="Choose defaults", button_text="Open", service=service)
        self.addCleanup(card.deleteLater)
        card.open_button.click()
        self.pump_until(lambda: not card.busy)
        self.assertIn("not installed", card.status_label.text())
        self.assertEqual(card.property("capabilityState"), "unavailable")
        self.assertFalse(card.open_button.isEnabled())
        self.assertTrue(card.check_button.isEnabled())
        launch.assert_not_called()

    @patch("ui.native_handoff_card.SystemManager.get_platform_profile", return_value=Mock())
    @patch("ui.native_handoff_card.QProcess.startDetached")
    def test_pending_native_launch_cannot_escape_shutdown(self, launch, _profile):
        entered, release = Event(), Event()
        service = Mock()
        def read(*_args, **_kwargs):
            entered.set()
            release.wait(2)
            return NativeHandoffLaunch("/usr/bin/kcmshell6", ("kcm_icons",))
        service.prepare_launch.side_effect = read
        card = ManagedNativeHandoffCard(NativeHandoffId.ICON_SETTINGS, title="Icons", description="Choose icons", button_text="Open", service=service)
        self.addCleanup(card.deleteLater)
        card.open_button.click()
        self.pump_until(entered.is_set)
        self.assertFalse(card.cleanup(0))
        release.set()
        self.pump_until(lambda: not card.busy)
        self.assertFalse(card.open_button.isEnabled())
        launch.assert_not_called()

    @patch("ui.native_handoff_card.SystemManager.get_platform_profile", return_value=Mock())
    @patch("ui.native_handoff_card.QProcess.startDetached", return_value=(True, 123))
    def test_native_open_revalidates_before_launching_fixed_vector(self, launch, _profile):
        service = Mock()
        service.prepare_launch.return_value = NativeHandoffLaunch("/usr/bin/kcmshell6", ("kcm_autostart",))
        card = ManagedNativeHandoffCard(NativeHandoffId.AUTOSTART_SETTINGS, title="Autostart", description="Manage startup", button_text="Open", service=service)
        self.addCleanup(card.deleteLater)
        card.open_button.click()
        self.pump_until(lambda: not card.busy)
        service.prepare_launch.assert_called_once()
        launch.assert_called_once_with("/usr/bin/kcmshell6", ["kcm_autostart"])
        self.assertIn("opened", card.status_label.text())

    def test_rpm_inventory_label_is_not_a_fedora_origin_claim(self):
        from services.software.installed_applications import InstalledApplication, InstalledInventory
        page = InstallWorkflowPage()
        self.addCleanup(page.deleteLater)
        page.installed_card.apply_inventory(InstalledInventory((InstalledApplication("External app", "third-party", "fedora", "system", "third-party"),)))
        row = page.installed_card._application_rows[0][1]
        self.assertIn("RPM", row.description_label.text())
        self.assertNotIn("Fedora", row.description_label.text())
        self.assertTrue(any(button.text() == "Open software manager" for button in row.findChildren(QPushButton)))


if __name__ == "__main__":
    unittest.main()
