"""V24 Flow contracts for Applications and Updates presentation."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication, QFrame, QPushButton

from ui.maintenance_updates import _UpdatesSubTab
from ui.software_tab import _ApplicationsSubTab


class TestV24ApplicationsFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    @patch("services.software.applications.SystemManager.is_atomic", return_value=False)
    @patch("ui.software_tab.SoftwareUtils.is_check_command_satisfied", return_value=False)
    def test_application_row_has_one_review_action_and_explicit_source(
        self,
        _installed: MagicMock,
        _atomic: MagicMock,
    ) -> None:
        tab = _ApplicationsSubTab()
        self.addCleanup(tab.deleteLater)
        tab.apps = [
            {
                "name": "Editor",
                "desc": "Text editor",
                "cmd": "pkexec",
                "args": ["dnf", "install", "-y", "editor"],
                "check_cmd": "rpm -q editor",
            }
        ]

        tab.refresh_list()

        row = tab.findChild(QFrame, "applicationRow")
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row.property("appSource"), "fedora")
        self.assertEqual(row.property("appStatus"), "available")
        actions = [button for button in row.findChildren(QPushButton) if button.property("buttonRole") == "primary"]
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].text(), "Review install")
        self.assertIsNotNone(row.findChild(QFrame, "applicationSourceBadge"))
        self.assertIsNotNone(row.findChild(QFrame, "applicationStatusBadge"))

    @patch("services.software.applications.SystemManager.is_atomic", return_value=False)
    def test_search_filter_empty_state_is_explicit(self, _atomic: MagicMock) -> None:
        tab = _ApplicationsSubTab()
        self.addCleanup(tab.deleteLater)
        tab.apps = [
            {
                "name": "Editor",
                "desc": "Text editor",
                "cmd": "pkexec",
                "args": ["dnf", "install", "-y", "editor"],
                "check_cmd": "rpm -q editor",
            }
        ]
        with patch.object(tab, "check_installed", return_value=False):
            tab.refresh_list()

        tab._search_bar.setText("does-not-exist")

        self.assertFalse(tab.filter_empty.isHidden())

    @patch("services.software.applications.SystemManager.is_atomic", return_value=False)
    def test_review_handoff_does_not_run_a_command(self, _atomic: MagicMock) -> None:
        tab = _ApplicationsSubTab()
        self.addCleanup(tab.deleteLater)
        requests: list[tuple[str, object]] = []
        tab.actionCenterRequested.connect(lambda action_id, parameters: requests.append((action_id, parameters)))
        entry = {
            "name": "Editor",
            "desc": "Text editor",
            "cmd": "pkexec",
            "args": ["dnf", "install", "-y", "editor"],
            "check_cmd": "rpm -q editor",
        }

        tab.run_app_action(entry, installed=False)

        self.assertEqual(requests, [("install-application", {"source": "fedora", "package_id": "editor"})])
        self.assertFalse(tab.runner.is_running())
        self.assertEqual(tab.application_feedback.property("resultKind"), "info")


class TestV24UpdatesFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    @patch("ui.maintenance_updates.SystemManager.get_package_manager", return_value="dnf")
    def test_update_lifecycle_distinguishes_check_available_and_review(self, _manager: MagicMock) -> None:
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

    @patch("ui.maintenance_updates.SystemManager.get_package_manager", return_value="rpm-ostree")
    def test_atomic_plan_explains_deployment_restart(self, _manager: MagicMock) -> None:
        tab = _UpdatesSubTab()
        self.addCleanup(tab.deleteLater)

        tab.run_dnf_update()

        self.assertIn("new Atomic deployment", tab._update_guidance())
        self.assertIn("Required to use the new deployment", tab.update_state.message_label.text())

    @patch("ui.maintenance_updates.SystemManager.get_package_manager", return_value="dnf")
    def test_terminal_and_cancelled_states_are_explicit(self, _manager: MagicMock) -> None:
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
