"""UI tests for the read-only repositories status page."""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLabel

from services.software.source_status import SourceScope, SourceState, SourceStatus, SourceStatusReason
from ui.software_tab import SoftwareTab, _RepositoriesSubTab


class TestRepositoryStatusUi(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.tab = _RepositoriesSubTab()

    def tearDown(self) -> None:
        self.tab.deleteLater()
        self.app.processEvents()

    def test_unchecked_sources_are_labeled_as_unchecked_with_accessible_names(self) -> None:
        label = self.tab.findChild(QLabel, "sourceStatus:flathub:user")

        self.assertEqual(label.text(), "Status not checked yet")
        self.assertEqual(label.property("sourceState"), "unknown")
        self.assertIn("Flathub user software source status", label.accessibleName())

    def test_status_text_and_accessible_name_include_source_scope_and_state(self) -> None:
        self.tab._apply_source_statuses(
            (
                SourceStatus("rpmfusion-free", SourceScope.SYSTEM, SourceState.ENABLED),
                SourceStatus("rpmfusion-nonfree", SourceScope.SYSTEM, SourceState.DISABLED),
                SourceStatus("loofi-copr", SourceScope.SYSTEM, SourceState.DISABLED),
                SourceStatus("flathub", SourceScope.SYSTEM, SourceState.DISABLED),
                SourceStatus("flathub", SourceScope.USER, SourceState.ENABLED),
            )
        )

        free = self.tab.findChild(QLabel, "sourceStatus:rpmfusion-free:system")
        user_flathub = self.tab.findChild(QLabel, "sourceStatus:flathub:user")
        self.assertIsNotNone(free)
        self.assertIn("RPM Fusion Free (system): Enabled", free.text())
        self.assertEqual(free.property("sourceState"), "enabled")
        self.assertIn("system source status: Enabled", free.accessibleName())
        self.assertIn("Flathub (user): Enabled", user_flathub.text())
        self.assertEqual(user_flathub.property("sourceState"), "enabled")

    def test_unknown_status_includes_a_reason_in_text_and_accessibility_description(self) -> None:
        self.tab._apply_source_statuses(
            (
                SourceStatus(
                    "flathub",
                    SourceScope.USER,
                    SourceState.UNKNOWN,
                    SourceStatusReason.TOOL_UNAVAILABLE,
                ),
            )
        )

        label = self.tab.findChild(QLabel, "sourceStatus:flathub:user")
        self.assertIn("Could not check", label.text())
        self.assertIn("required tool is not installed", label.text())
        self.assertEqual(label.accessibleDescription(), label.text())
        self.assertEqual(label.property("sourceState"), "unknown")

    def test_missing_result_rows_become_unknown_instead_of_disabled(self) -> None:
        self.tab._apply_source_statuses(())

        for label in self.tab._source_status_labels.values():
            self.assertEqual(label.property("sourceState"), "unknown")

    def test_setup_buttons_open_manual_action_center_guidance(self) -> None:
        emitted: list[tuple[str, object]] = []
        self.tab.actionCenterRequested.connect(lambda action_id, params: emitted.append((action_id, params)))

        self.tab.btn_rpm_fusion_guidance.click()
        self.tab.btn_codec_guidance.click()
        self.tab.btn_flathub_guidance.click()
        self.tab.btn_loofi_copr_guidance.click()

        self.assertEqual(
            emitted,
            [
                ("enable-rpm-fusion", {}),
                ("install-multimedia-codecs", {}),
                ("enable-flathub", {}),
                ("enable-loofi-copr", {}),
            ],
        )
        for button in (
            self.tab.btn_rpm_fusion_guidance,
            self.tab.btn_codec_guidance,
            self.tab.btn_flathub_guidance,
            self.tab.btn_loofi_copr_guidance,
        ):
            self.assertNotIn("Enable", button.text())
            self.assertTrue(button.accessibleName())
            self.assertTrue(button.focusPolicy() & Qt.FocusPolicy.TabFocus)

    @patch("ui.operation_worker.OperationControllerQtAdapter.start", return_value=True)
    def test_refresh_runs_the_status_service_in_the_worker_adapter(self, start) -> None:
        self.tab.refresh_source_status()

        start.assert_called_once()
        operation = start.call_args.args[0]
        self.assertEqual(operation.__self__, self.tab._source_status_service)
        self.assertEqual(operation.__name__, "snapshot")
        self.assertTrue(all(label.property("sourceState") == "unknown" for label in self.tab._source_status_labels.values()))

    def test_repository_route_activation_refreshes_its_page(self) -> None:
        repositories = MagicMock()
        fake_tab = SimpleNamespace(
            _route_active=True,
            tabs=SimpleNamespace(currentIndex=lambda: 1),
            _applications_tab=MagicMock(),
            _repositories_tab=repositories,
        )

        SoftwareTab._activate_current_subtab(fake_tab)

        repositories.on_activate.assert_called_once_with()
        fake_tab._applications_tab.on_activate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
