"""Phase 7 onboarding lifecycle, data-preservation, and layout tests."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QScrollArea, QStackedWidget

from services.system.onboarding import collect_welcome_system_summary


def _summary():
    return MagicMock(
        fedora_name="Fedora Linux 44 (KDE Plasma Desktop)",
        fedora_version="44",
        variant="KDE Plasma Desktop",
        package_manager="dnf",
        deployment_mode="Traditional",
        behavior="DNF transactions use preview and confirmation.",
        support_status="Supported",
        support_detail="Fedora 44 is verified.",
    )


class TestWelcomeSystemSummary(unittest.TestCase):
    def test_traditional_fedora_44_contract(self):
        summary = collect_welcome_system_summary(
            release={"PRETTY_NAME": "Fedora 44", "VERSION_ID": "44", "VARIANT": "Workstation"},
            atomic=False,
        )
        self.assertEqual(summary.package_manager, "dnf")
        self.assertEqual(summary.deployment_mode, "Traditional")
        self.assertEqual(summary.support_status, "Supported")
        self.assertIn("transaction", summary.behavior)

    def test_atomic_fedora_45_is_preview_and_staged(self):
        summary = collect_welcome_system_summary(
            release={"PRETTY_NAME": "Fedora Kinoite 45", "VERSION_ID": "45", "VARIANT": "Kinoite"},
            atomic=True,
        )
        self.assertEqual(summary.package_manager, "rpm-ostree")
        self.assertEqual(summary.deployment_mode, "Atomic")
        self.assertEqual(summary.support_status, "Preview")
        self.assertIn("staged", summary.behavior)
        self.assertIn("reboot", summary.behavior)

    def test_other_and_unknown_releases_are_not_claimed_supported(self):
        outside = collect_welcome_system_summary(
            release={"VERSION_ID": "43", "VARIANT": "Workstation"}, atomic=False
        )
        unknown = collect_welcome_system_summary(
            release={"VARIANT": "Workstation"}, atomic=False
        )
        self.assertEqual(outside.support_status, "Not verified")
        self.assertEqual(unknown.support_status, "Unknown")


class TestFirstRunWelcome(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    @patch("ui.wizard.collect_welcome_system_summary", return_value=_summary())
    def test_single_responsive_page_with_primary_action(self, _mock_summary):
        from ui.wizard import FirstRunWelcome

        welcome = FirstRunWelcome()
        self.assertEqual(welcome.findChildren(QStackedWidget), [])
        scroll = welcome.findChild(QScrollArea, "welcomeScroll")
        self.assertIsNotNone(scroll)
        self.assertTrue(scroll.widgetResizable())
        self.assertTrue(welcome.open_button.isDefault())
        self.assertEqual(welcome.open_button.accessibleName(), "Open Loofi")
        self.assertEqual(welcome.details_button.accessibleName(), "View system details")
        self.assertLessEqual(welcome.minimumHeight(), 720)
        welcome.close()

    @patch("ui.wizard._mark_first_run_complete")
    @patch("ui.wizard.collect_welcome_system_summary", return_value=_summary())
    def test_open_loofi_only_completes_welcome(self, _mock_summary, mock_complete):
        from ui.wizard import FirstRunWelcome

        welcome = FirstRunWelcome()
        welcome._open_loofi()
        mock_complete.assert_called_once_with()
        self.assertEqual(welcome.requested_route, "")

    @patch("ui.wizard._mark_first_run_complete")
    @patch("ui.wizard.collect_welcome_system_summary", return_value=_summary())
    def test_view_details_requests_stable_system_route(self, _mock_summary, mock_complete):
        from ui.wizard import FirstRunWelcome

        welcome = FirstRunWelcome()
        welcome._open_system_details()
        mock_complete.assert_called_once_with()
        self.assertEqual(welcome.requested_route, "system_info")

    @patch("ui.wizard._mark_first_run_complete")
    @patch("ui.wizard.collect_welcome_system_summary", return_value=_summary())
    def test_reject_does_not_complete_onboarding(self, _mock_summary, mock_complete):
        from ui.wizard import FirstRunWelcome

        welcome = FirstRunWelcome()
        welcome.reject()
        mock_complete.assert_not_called()

    @patch("ui.wizard.collect_welcome_system_summary", return_value=_summary())
    def test_high_scale_font_keeps_actions_available(self, _mock_summary):
        from ui.wizard import FirstRunWelcome

        welcome = FirstRunWelcome()
        font = QFont(welcome.font())
        font.setPointSizeF(max(18.0, font.pointSizeF() * 2.0))
        welcome.setFont(font)
        welcome.resize(640, 480)
        self.assertTrue(welcome.open_button.isEnabled())
        self.assertTrue(welcome.details_button.isEnabled())
        self.assertGreaterEqual(welcome.minimumWidth(), 520)
        welcome.close()

    @patch("ui.wizard.collect_welcome_system_summary", return_value=_summary())
    def test_completion_preserves_existing_profile_and_settings_bytes(self, _mock_summary):
        import ui.wizard as wizard

        with tempfile.TemporaryDirectory() as tmpdir:
            config = Path(tmpdir)
            files = {
                "profile.json": b'{"use_case":"daily"}\n',
                "wizard_v2.json": b'{"selected_actions":["keep"]}\n',
                "settings.json": b'{"navigation_mode":"advanced"}\n',
            }
            for name, data in files.items():
                (config / name).write_bytes(data)

            original_config = wizard._CONFIG_DIR
            original_sentinel = wizard._FIRST_RUN_SENTINEL
            try:
                wizard._CONFIG_DIR = config
                wizard._FIRST_RUN_SENTINEL = config / "first_run_complete"
                welcome = wizard.FirstRunWelcome()
                welcome._open_loofi()
            finally:
                wizard._CONFIG_DIR = original_config
                wizard._FIRST_RUN_SENTINEL = original_sentinel

            self.assertTrue((config / "first_run_complete").exists())
            for name, data in files.items():
                self.assertEqual((config / name).read_bytes(), data)


if __name__ == "__main__":
    unittest.main()
