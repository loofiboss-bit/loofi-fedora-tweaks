"""Focused V22 Phase 3 visual-hierarchy contracts."""

from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication, QLabel, QPushButton

from core.navigation import ADVANCED_DESTINATION, NavigationContext, NavigationMode
from ui.activity_recovery_tab import ActivityRecoveryTab
from ui.maintenance_action_center import _ActionCenterSubTab
from ui.navigation.destination_host import DestinationHost
from ui.system_check_tab import SystemCheckTab


ROOT = Path(__file__).parents[1]


class TestV22Phase3AlignmentUi(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_structural_backgrounds_keep_labels_transparent(self) -> None:
        qss = (
            ROOT / "loofi-fedora-tweaks" / "assets" / "base.qss"
        ).read_text(encoding="utf-8")

        self.assertIn("QLabel {\n    background-color: transparent;", qss)
        self.assertIn("QMainWindow,\nQDialog,\nQAbstractScrollArea {", qss)
        self.assertNotIn(
            "QWidget {\n    background-color: $color_window;",
            qss,
        )

    def test_specialist_tools_start_with_group_overview_and_have_zero_state(
        self,
    ) -> None:
        host = DestinationHost()
        host.set_destination(
            ADVANCED_DESTINATION,
            NavigationContext(mode=NavigationMode.ADVANCED),
        )

        self.assertTrue(host.navigator.group_overview.isVisibleTo(host))
        self.assertFalse(host.navigator.rail.isVisible())
        self.assertGreaterEqual(len(host.navigator._group_buttons), 6)

        host.navigator.filter_input.setText("no-such-specialist-tool")
        self.app.processEvents()

        self.assertTrue(host.navigator.no_results.isVisibleTo(host))
        self.assertEqual(host.navigator.visible_section_ids(), ())
        host.deleteLater()

    @patch.object(
        _ActionCenterSubTab,
        "_start_operation",
        autospec=True,
        side_effect=lambda _tab, operation, on_success, _title: on_success(
            operation()
        ),
    )
    @patch("core.actions.center.ActionCenterService")
    def test_action_center_exposes_one_primary_and_defers_preview_target(
        self,
        service_cls: MagicMock,
        _start_operation: MagicMock,
    ) -> None:
        item = SimpleNamespace(
            id="fstrim-all",
            title="Trim filesystems",
            source="catalog:v18",
            description="Review filesystem trim.",
            risk_level="low",
            privilege="none",
            command_preview=(),
            verification_command=(),
            rollback_hint="No rollback required.",
            manual_only=False,
            state="available",
            metadata={},
        )
        service_cls.return_value.catalog_items.return_value = [item]
        service_cls.return_value.candidates_from_readiness.return_value = []

        tab = _ActionCenterSubTab()
        primary = [
            button
            for button in tab.findChildren(QPushButton)
            if button.isVisibleTo(tab)
            and button.objectName() == "primaryAction"
        ]

        self.assertEqual([button.text() for button in primary], ["Review & Plan"])
        self.assertTrue(tab.load_preview_button.isHidden())
        self.assertIn("Upgrade Assistant", tab.target_guidance.text())
        tab.deleteLater()

    def test_activity_initial_state_centers_its_only_load_action(self) -> None:
        service = SimpleNamespace(snapshot=MagicMock())
        tab = ActivityRecoveryTab(journal_service=service)

        self.assertTrue(tab.empty_load_button.isVisibleTo(tab))
        self.assertFalse(tab.activity_actions.isVisible())
        self.assertEqual(
            tab.empty_load_button.property("buttonRole"),
            "primary",
        )
        service.snapshot.assert_not_called()
        tab.deleteLater()

    def test_system_check_has_visible_local_view_label(self) -> None:
        state = SimpleNamespace(
            latest_check_id="",
            latest_state="unavailable",
            latest_completed_at=None,
            atomic=False,
            findings=(),
            history=(),
            metrics=(),
            maintenance_outcomes=(),
            unavailable_sources=(),
            snapshot_error="",
            metric_error="",
        )
        service = SimpleNamespace(load=MagicMock(return_value=state))
        tab = SystemCheckTab(presentation_service=service)
        label = tab.findChild(QLabel, "systemCheckViewLabel")

        self.assertIsNotNone(label)
        assert label is not None
        self.assertEqual(label.text(), "View")
        self.assertFalse(label.isHidden())
        tab.deleteLater()

    def test_shell_toggle_uses_panel_semantics_instead_of_back_arrow(
        self,
    ) -> None:
        source = (
            ROOT / "loofi-fedora-tweaks" / "ui" / "main_window_interactions.py"
        ).read_text(encoding="utf-8")

        self.assertIn("SP_TitleBarShadeButton", source)
        self.assertIn("SP_TitleBarUnshadeButton", source)
        self.assertNotIn("SP_ArrowLeft if collapsed", source)


if __name__ == "__main__":
    unittest.main()
