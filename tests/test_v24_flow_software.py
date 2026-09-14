"""V24 Flow contracts for Applications and Updates presentation."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication

from ui.maintenance_updates import _UpdatesSubTab
from ui.software_tab import _ApplicationsSubTab


class TestV24ApplicationsFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_application_page_delegates_to_native_store(self) -> None:
        tab = _ApplicationsSubTab()
        self.addCleanup(tab.deleteLater)
        self.assertEqual(tab.native_handoff.handoff_id.value, "software.center")
        self.assertTrue(tab.catalog_empty.property("handoffOnly"))
        self.assertEqual(tab.load_apps(), [])
        self.assertFalse(hasattr(tab, "run_app_action"))


class TestV24UpdatesFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    @patch("ui.maintenance_updates.SystemManager.get_platform_profile", return_value=MagicMock(
        deployment_backend=MagicMock(value="dnf5"),
        package_manager_name="dnf5",
    ))
    def test_update_lifecycle_distinguishes_check_available_and_review(self, _profile: MagicMock) -> None:
        tab = _UpdatesSubTab()
        self.addCleanup(tab.deleteLater)
        requests: list[tuple[str, object]] = []
        tab.actionCenterRequested.connect(lambda action_id, parameters: requests.append((action_id, parameters)))

        tab.set_checking("Fedora system packages")
        self.assertEqual(tab.update_state.property("updateLifecycleState"), "checking")
        tab.set_updates_available("Fedora system packages", 4)
        self.assertEqual(tab.update_state.property("updateLifecycleState"), "available")
        tab.run_dnf_update()

        self.assertEqual(tab.update_state.property("updateLifecycleState"), "review")
        self.assertEqual(requests, [("update-fedora-system", {})])
        self.assertFalse(tab.runner.is_running())

    @patch("ui.maintenance_updates.SystemManager.get_platform_profile", return_value=MagicMock(
        deployment_backend=MagicMock(value="rpm_ostree"),
        package_manager_name="rpm-ostree",
    ))
    def test_atomic_plan_explains_deployment_restart(self, _profile: MagicMock) -> None:
        tab = _UpdatesSubTab()
        self.addCleanup(tab.deleteLater)

        tab.run_dnf_update()

        self.assertIn("new Atomic deployment", tab._update_guidance())
        self.assertIn("Required to use the new deployment", tab.update_state.message_label.text())

    @patch("ui.maintenance_updates.SystemManager.get_platform_profile", return_value=MagicMock(
        deployment_backend=MagicMock(value="dnf5"),
        package_manager_name="dnf5",
    ))
    def test_terminal_and_cancelled_states_are_explicit(self, _profile: MagicMock) -> None:
        tab = _UpdatesSubTab()
        self.addCleanup(tab.deleteLater)

        tab.on_command_finished(1)
        self.assertEqual(tab.update_state.property("updateLifecycleState"), "failed")
        with patch.object(tab.runner, "stop") as stop:
            tab._cancel_command()
        stop.assert_called_once_with()
        self.assertEqual(tab.update_state.property("updateLifecycleState"), "cancelled")


if __name__ == "__main__":
    unittest.main()
