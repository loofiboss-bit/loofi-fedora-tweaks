"""v25 Proof GUI integration keeps direct execution on Action Center authority."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication

from core.actions.direct import DirectActionResult
from core.actions.eligibility import EligibilityDecision
from core.actions.outcomes import OutcomeSummary, RecoveryReadiness
from core.settings.execution import ExecutionSettings
from ui.maintenance_action_center import _ActionCenterSubTab


def _item() -> SimpleNamespace:
    return SimpleNamespace(
        id="dnf-clean-all",
        title="Clean package cache",
        description="Remove stale package cache data.",
        manual_only=False,
        command_preview=(),
        verification_command=(),
        metadata={"affected_resources": ("package-cache",), "reboot_policy": "none"},
        privilege="administrator",
        rollback_hint="Refresh package metadata if needed.",
        source="catalog:v18",
        risk_level="low",
    )


class _SettingsStore:
    def load(self):
        return ExecutionSettings()


class TestV25GuiDirectAction(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    @patch.object(_ActionCenterSubTab, "_load_target")
    def test_eligible_queue_item_exposes_proof_primary(self, _load: MagicMock) -> None:
        tab = _ActionCenterSubTab()
        self.addCleanup(tab.deleteLater)
        item = _item()
        tab._items = [item]
        tab._visible_records = [("candidate", item)]
        tab.action_list = MagicMock()
        tab.action_list.currentRow.return_value = 0

        service = MagicMock()
        service.eligibility_for.return_value = EligibilityDecision(
            "dnf-clean-all",
            "direct",
            True,
            "low_risk_direct",
            "Ready",
            risk_level="low",
            metadata_complete=True,
        )
        service.settings_store = _SettingsStore()
        tab._direct_service = service
        tab._show_item(item)

        self.assertTrue(tab.direct_button.isVisibleTo(tab))
        self.assertEqual(tab.direct_button.objectName(), "primaryAction")

    @patch.object(
        _ActionCenterSubTab,
        "_start_operation",
        autospec=True,
        side_effect=lambda _tab, operation, on_success, _title: on_success(operation()),
    )
    @patch("ui.maintenance_action_center.QMessageBox.warning")
    @patch.object(_ActionCenterSubTab, "_load_target")
    def test_direct_click_uses_typed_service_and_not_runner(
        self,
        _load: MagicMock,
        warning: MagicMock,
        _operation: MagicMock,
    ) -> None:
        tab = _ActionCenterSubTab()
        self.addCleanup(tab.deleteLater)
        item = _item()
        tab._items = [item]
        tab._visible_records = [("candidate", item)]
        tab.action_list = MagicMock()
        tab.action_list.currentRow.return_value = 0
        result = DirectActionResult(
            action_id="dnf-clean-all",
            status="completed_verified",
            message="Verified.",
            eligibility=EligibilityDecision(
                "dnf-clean-all", "direct", True, "low_risk_direct", "Ready", risk_level="low"
            ),
            outcome=OutcomeSummary(
                "dnf-clean-all",
                "plan-1",
                "run-1",
                "corr-1",
                "verified",
                "verification-succeeded",
                recovery=RecoveryReadiness(False, "manual_guidance"),
            ),
            plan_id="",
            run_id="",
        )
        service = MagicMock()
        service.eligibility_for.return_value = result.eligibility
        service.settings_store = _SettingsStore()
        service.run.return_value = result
        tab._direct_service = service
        tab._show_item(item)
        tab.runner.run_command = MagicMock()

        tab._run_direct_selected()

        service.run.assert_called_once_with(
            "dnf-clean-all",
            {},
            finding_context=None,
            confirmed=True,
            target=tab._target_key,
        )
        tab.runner.run_command.assert_not_called()
        self.assertIn("Completed and verified", tab.selected_summary.text())
        warning.assert_not_called()


if __name__ == "__main__":
    unittest.main()
