"""V24 Action Center master-detail and explicit-execution regressions."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication, QPushButton, QSplitter

from ui.action_center_presentation import action_center_group_for_state
from ui.maintenance_action_center import _ActionCenterSubTab


def _item() -> SimpleNamespace:
    return SimpleNamespace(
        id="dnf-clean-all",
        title="Clean package cache",
        description="Remove cached package metadata after review.",
        manual_only=False,
        command_preview=(),
        verification_command=("du", "-s", "/var/cache/dnf"),
        metadata={"affected_resources": ("package-cache",), "reboot_policy": "none"},
        privilege="administrator",
        rollback_hint="Refresh package metadata if needed.",
        source="catalog:v18",
        risk_level="low",
    )


class TestV24ActionCenterFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    @patch.object(_ActionCenterSubTab, "_load_target")
    def test_review_queue_is_initial_and_catalog_is_separate(self, _load: MagicMock) -> None:
        tab = _ActionCenterSubTab()
        self.addCleanup(tab.deleteLater)

        self.assertEqual(tab.mode_switcher.active_view_id(), "queue")
        self.assertEqual(tab.mode_switcher.view_ids(), ("queue", "catalog"))
        self.assertIsNotNone(tab.findChild(QSplitter, "actionCenterMasterDetail"))
        self.assertEqual(tab.lifecycle_view.count(), 6)

    @patch.object(_ActionCenterSubTab, "_load_target")
    def test_catalog_browse_select_and_preview_do_not_plan_or_execute(self, _load: MagicMock) -> None:
        tab = _ActionCenterSubTab()
        self.addCleanup(tab.deleteLater)
        tab._items = [_item()]
        tab._orchestrator = MagicMock()
        tab._service.preview = MagicMock()
        tab.runner.run_command = MagicMock()

        tab._show_master_mode("catalog")
        tab.action_list.setCurrentRow(0)
        self.assertIn("Affected components: package-cache", tab.selected_summary.text())
        tab._preview_selected()

        tab._orchestrator.plan.assert_not_called()
        tab._orchestrator.prepare_run.assert_not_called()
        tab.runner.run_command.assert_not_called()
        self.assertIn("fresh preflight", tab.selected_summary.text())
        visible_primary = [
            button
            for button in tab.findChildren(QPushButton)
            if button.isVisibleTo(tab) and button.objectName() == "primaryAction"
        ]
        self.assertEqual([button.text() for button in visible_primary], ["Review & Plan"])

    @patch.object(
        _ActionCenterSubTab,
        "_start_operation",
        autospec=True,
        side_effect=lambda _tab, operation, on_success, _title: on_success(operation()),
    )
    @patch.object(_ActionCenterSubTab, "_load_target")
    def test_review_creates_plan_but_never_prepares_or_runs_it(
        self,
        _load: MagicMock,
        _operation: MagicMock,
    ) -> None:
        tab = _ActionCenterSubTab()
        self.addCleanup(tab.deleteLater)
        item = _item()
        tab._items = [item]
        tab._visible_records = [("candidate", item)]
        tab.master_pane.populate_catalog([item])
        tab.action_list.setCurrentRow(0)
        policy = SimpleNamespace(reason_code="preflight-ok", explanation="Ready after review")
        plan = SimpleNamespace(
            plan_id="plan-1",
            action_id=item.id,
            state="ready",
            affected_resources=("package-cache",),
            privileged=True,
            reboot_policy="none",
            risk_level="low",
            policy_decision=policy,
            recovery_guidance=item.rollback_hint,
            preview=("dnf", "clean", "all"),
            expires_at=100.0,
            finding_context=None,
        )
        tab._orchestrator = MagicMock()
        tab._orchestrator.plan.return_value = plan
        tab.runner.run_command = MagicMock()

        tab._plan_selected()

        tab._orchestrator.plan.assert_called_once()
        tab._orchestrator.prepare_run.assert_not_called()
        tab.runner.run_command.assert_not_called()
        self.assertEqual(tab._current_plan, plan)

    def test_persisted_states_keep_six_groups_and_explain_edge_states(self) -> None:
        self.assertEqual(action_center_group_for_state("draft"), "needs_review")
        self.assertEqual(action_center_group_for_state("cancelled"), "failed")
        self.assertEqual(action_center_group_for_state("unavailable"), "failed")

    @patch("core.actions.ActionRunStore")
    @patch("core.actions.ActionPlanStore")
    @patch.object(_ActionCenterSubTab, "_load_target")
    def test_nonempty_state_replaces_stale_empty_banner(
        self,
        _load: MagicMock,
        plan_store: MagicMock,
        run_store: MagicMock,
    ) -> None:
        tab = _ActionCenterSubTab()
        self.addCleanup(tab.deleteLater)
        plan_store.return_value.list.return_value = [
            SimpleNamespace(plan_id="plan-1", action_id="dnf-clean-all", state="ready")
        ]
        run_store.return_value.list.return_value = []
        tab.master_pane.add_record = MagicMock()
        tab.presentation_banner.set_result(
            "success",
            "Nothing needs review",
            "No planned maintenance item needs review right now.",
        )

        tab._show_lifecycle_view(1)

        self.assertEqual(tab.presentation_banner.title_label.text(), "Ready changes")
        self.assertIn("1 change is currently in ready", tab.presentation_banner.message_label.text())


if __name__ == "__main__":
    unittest.main()
