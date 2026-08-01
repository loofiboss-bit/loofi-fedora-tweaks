"""Focused UI contracts for the v23.1 core workflow simplification."""

from __future__ import annotations

import inspect
import os
import sys
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"),
)

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon, QPixmap
from PyQt6.QtWidgets import QApplication, QGroupBox, QWidget

from core.home import HomeSummary
from core.workflows import ReclaimAnalysisService
from ui.atlas_dashboard_tab import AtlasDashboardTab
from ui.design.theme_manager import ThemeManager
from ui.maintenance_action_center import (
    ACTION_CENTER_STATE_GROUPS,
    _ActionCenterSubTab,
    action_center_group_for_state,
)
from ui.maintenance_updates import _CleanupSubTab, _UpdatesSubTab
from ui.settings_tab import SettingsTab
from ui.troubleshoot_widget import TroubleshootWidget


def _empty_home_summary(*, data_state: str = "empty") -> HomeSummary:
    return HomeSummary(
        overall_state="unknown",
        data_state=data_state,
        summary=(
            "No saved system status exists yet."
            if data_state == "empty"
            else "Some saved status sources could not be read."
        ),
        generated_at=datetime.now(timezone.utc),
        primary_recommendation=None,
        attention_items=(),
        common_tasks=(),
        recent_change=None,
        source_errors=("saved status failed",) if data_state == "error" else (),
        status_items=(),
        freshness_state="unavailable",
    )


class TestPhase3HomeAndTroubleshoot(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_home_consolidates_unavailable_status_and_distinguishes_failure(self):
        provider = SimpleNamespace(summary=lambda: _empty_home_summary())
        tab = AtlasDashboardTab(home_service=provider)
        self.addCleanup(tab.deleteLater)

        self.assertFalse(tab.status_unavailable.isHidden())
        self.assertTrue(tab.status_grid.isHidden())
        self.assertEqual(tab.status_unavailable.title_label.text(), "Not checked yet")
        self.assertNotIn("Status unavailable", tab.status_unavailable.message_label.text())

        provider.summary = lambda: _empty_home_summary(data_state="error")
        tab.refresh_summary()

        self.assertEqual(tab.status_unavailable.title_label.text(), "Status check failed")
        self.assertIn("Check failed", tab.freshness_label.text())

    def test_home_keeps_the_five_core_workflows_visible(self):
        from core.home.service import _COMMON_TASKS

        self.assertEqual(
            [task.id for task in _COMMON_TASKS],
            [
                "updates",
                "applications",
                "troubleshoot",
                "cleanup",
                "planned-changes",
            ],
        )

    def test_troubleshoot_starts_from_eight_plain_language_symptoms(self):
        widget = TroubleshootWidget(history=SimpleNamespace(latest=lambda: (None, "")))
        self.addCleanup(widget.deleteLater)

        labels = [
            widget.profile_selector.itemText(index)
            for index in range(widget.profile_selector.count())
        ]
        self.assertEqual(
            labels,
            [
                "No internet",
                "Sound is not working",
                "Bluetooth is not working",
                "Updates failed",
                "An app will not start",
                "The system feels slow",
                "Storage is full",
                "Something else",
            ],
        )
        self.assertEqual(widget.profile_label.text(), "What is going wrong?")
        self.assertFalse(widget.technical_disclosure.toggle_button.isChecked())
        self.assertNotIn("seconds", widget.checks_label.text())
        self.assertNotIn("required", widget.checks_label.text())

    def test_860_width_140_percent_rtl_and_high_contrast_keep_start_reachable(self):
        original_font = self.app.font()
        theme_manager = ThemeManager()
        try:
            self.assertTrue(theme_manager.apply(self.app, "highcontrast"))
            font = QFont(original_font)
            font.setPointSizeF(original_font.pointSizeF() * 1.4)
            self.app.setFont(font)

            widget = TroubleshootWidget(history=SimpleNamespace(latest=lambda: (None, "")))
            self.addCleanup(widget.deleteLater)
            widget.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            widget.resize(860, 900)
            widget.show()
            self.app.processEvents()
            widget.start_button.setFocus()

            self.assertTrue(widget.start_button.isVisible())
            self.assertTrue(widget.start_button.hasFocus())
            self.assertLessEqual(
                widget.start_button.mapTo(
                    widget,
                    widget.start_button.rect().topRight(),
                ).x(),
                widget.width(),
            )
            self.assertEqual(
                widget.layoutDirection(),
                Qt.LayoutDirection.RightToLeft,
            )
        finally:
            self.app.setFont(original_font)
            theme_manager.apply(self.app, "system")


class TestPhase3PlansAndCleanup(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_action_center_uses_the_six_state_led_groups(self):
        self.assertEqual(
            [label for _group_id, label in ACTION_CENTER_STATE_GROUPS],
            [
                "Needs review",
                "Ready",
                "Running",
                "Waiting for restart",
                "Completed",
                "Failed",
            ],
        )
        expected = {
            "needs_review": "needs_review",
            "ready": "ready",
            "running": "running",
            "verifying": "running",
            "awaiting_reboot": "waiting_restart",
            "succeeded": "completed",
            "verification_failed": "failed",
        }
        self.assertEqual(
            {state: action_center_group_for_state(state) for state in expected},
            expected,
        )

    @patch.object(_ActionCenterSubTab, "_load_target")
    def test_action_center_hides_advanced_tools_and_definition_details_by_default(
        self,
        _mock_load_target,
    ):
        tab = _ActionCenterSubTab()
        self.addCleanup(tab.deleteLater)

        self.assertEqual(tab.lifecycle_view.count(), 6)
        self.assertFalse(tab.advanced_review_tools.toggle_button.isChecked())
        self.assertFalse(tab.detail_disclosure.toggle_button.isChecked())
        self.assertNotIn("definition", tab.scaffold.accessibleName().lower())

    @patch("core.actions.ActionRunStore.list", return_value=[])
    @patch("core.actions.ActionPlanStore.list", return_value=[])
    @patch.object(_ActionCenterSubTab, "_load_target")
    def test_action_center_catalog_candidates_require_explicit_advanced_choice(
        self,
        _mock_load_target,
        _mock_plan_list,
        _mock_run_list,
    ):
        tab = _ActionCenterSubTab()
        self.addCleanup(tab.deleteLater)
        candidate = SimpleNamespace(
            id="dnf-clean-all",
            title="Clean package cache",
            manual_only=False,
        )
        tab._items = [candidate]
        tab.action_list.blockSignals(True)

        tab._show_lifecycle_view(0)
        self.assertEqual(tab._visible_records, [])

        tab._requested_action_id = "dnf-clean-all"
        tab._show_lifecycle_view(0)
        self.assertEqual(tab._visible_records, [("candidate", candidate)])
        self.assertEqual(tab._action_title("dnf-clean-all"), "Clean package cache")
        self.assertEqual(tab._action_title("unknown-action"), "Unknown Action")
        tab.action_list.blockSignals(False)

    @patch(
        "ui.maintenance_updates.SystemManager.get_package_manager",
        return_value="rpm-ostree",
    )
    def test_updates_explain_restart_and_verification_before_action_center(
        self,
        _mock_package_manager,
    ):
        tab = _UpdatesSubTab()
        self.addCleanup(tab.deleteLater)
        requests = []
        tab.actionCenterRequested.connect(
            lambda action_id, parameters: requests.append((action_id, parameters))
        )

        tab.run_dnf_update()

        self.assertEqual(requests, [("update-fedora-system", {})])
        message = tab.update_state.message_label.text()
        self.assertIn("Restart:", message)
        self.assertIn("Verification:", message)

    def test_cleanup_previews_first_and_keeps_advanced_choices_closed(self):
        tab = _CleanupSubTab()
        self.addCleanup(tab.deleteLater)

        first_widget = tab.scaffold.content_layout.itemAt(0).widget()
        advanced = tab.findChild(QGroupBox, "cleanupAdvancedChoices")
        self.assertIsInstance(first_widget, QGroupBox)
        self.assertEqual(first_widget.title(), "Reclaim Preview")
        self.assertIsNotNone(advanced)
        self.assertFalse(advanced.isChecked())

        analysis = ReclaimAnalysisService.build(
            atomic=False,
            package_cache_bytes=1024,
            journal_bytes=2048,
        )
        selected = [
            category.id
            for category in analysis.categories
            if category.selected_by_default
        ]
        self.assertEqual(selected, ["package-cache"])


class TestPhase3ShellAndSettings(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    @staticmethod
    def _settings_manager() -> MagicMock:
        manager = MagicMock()
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
        manager.get.side_effect = lambda key, default=None: values.get(key, default)
        return manager

    @patch("ui.settings_tab.SettingsManager.instance")
    def test_settings_content_is_bounded_to_readable_width(self, mock_instance):
        mock_instance.return_value = self._settings_manager()
        tab = SettingsTab()
        self.addCleanup(tab.deleteLater)

        content_pages = tab.findChildren(QWidget, "settingsContent")
        self.assertEqual(len(content_pages), 5)
        self.assertTrue(all(page.maximumWidth() == 700 for page in content_pages))

    def test_main_window_title_does_not_include_version(self):
        from ui.main_window import MainWindow

        source = inspect.getsource(MainWindow._configure_window_surface)
        self.assertIn('setWindowTitle(self.tr("Loofi Fedora Tweaks"))', source)
        self.assertNotIn("__version__", source)

    @patch("ui.icon_pack.resolve_icon_path")
    @patch("ui.icon_pack.QIcon.fromTheme")
    def test_theme_icon_is_preferred_before_custom_fallback(
        self,
        mock_from_theme,
        mock_resolve_path,
    ):
        from ui.icon_pack import get_qicon

        pixmap = QPixmap(2, 2)
        pixmap.fill(Qt.GlobalColor.white)
        mock_from_theme.return_value = QIcon(pixmap)

        icon = get_qicon("home")

        self.assertFalse(icon.isNull())
        mock_from_theme.assert_called_once_with("go-home")
        mock_resolve_path.assert_not_called()


if __name__ == "__main__":
    unittest.main()
