"""Saved update hydration never repeats transactions or hides pending runs."""

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from core.actions.contracts import ActionRun
from core.tasks.update_flow import UpdateOverviewState, UpdateSourceState, update_cta
from services.software.update_overview import UpdateItem, UpdateOverviewSnapshot, UpdateSourceResult
from services.software.update_recovery import UpdateRecoveryService


class TestUpdateRecovery(unittest.TestCase):
    def setUp(self):
        self.overview = Mock()
        self.overview.load.return_value = UpdateOverviewSnapshot()
        self.runs = Mock()
        self.runs.list_read_only.return_value = []
        self.plans = Mock()
        self.plans.list_read_only.return_value = []
        self.service = UpdateRecoveryService(self.overview, self.runs, self.plans)

    def add_run(self, state, action="update-fedora-system", identifier="saved", timestamp=100):
        run = ActionRun(identifier, "plan-" + identifier, action, "correlation", state=state, updated_at=timestamp)
        self.runs.list_read_only.return_value.append(run)
        self.plans.list_read_only.return_value.append(SimpleNamespace(plan_id=run.plan_id, action_id=action))
        return run

    def test_empty_history_does_not_query_or_execute_host(self):
        state = self.service.load()
        self.assertEqual(state.source("system").status, "unchecked")
        self.overview.check.assert_not_called()
        self.runs.list_read_only.assert_called_once_with(strict=True)
        self.plans.list_read_only.assert_called_once_with()

    def test_pending_run_keeps_identity_before_and_after_reopen(self):
        for status, label in (("awaiting_reboot", "Continue"), ("verifying", "Verify")):
            with self.subTest(status=status):
                self.runs.list_read_only.return_value = []
                run = self.add_run(status)
                state = self.service.load().source("system")
                self.assertEqual(state.run_id, run.run_id)
                self.assertEqual(update_cta(state).label, label)
                self.assertEqual(self.service.load().source("system"), state)
                self.overview.check.assert_not_called()

    def test_pending_run_is_not_hidden_by_a_newer_terminal_run(self):
        run = self.add_run("awaiting_reboot")
        self.add_run("succeeded", identifier="newer", timestamp=200)
        self.assertEqual(self.service.load().source("system").run_id, run.run_id)

    def test_sources_are_restored_independently(self):
        self.add_run("verifying", "update-flatpaks", "flatpak")
        self.add_run("awaiting_reboot", "update-firmware", "firmware")
        state = self.service.load()
        self.assertEqual(state.source("system").status, "unchecked")
        self.assertEqual(state.cta("flatpak").action, "verify")
        self.assertEqual(state.cta("firmware").action, "continue")

    def test_terminal_or_interrupted_runs_go_to_review(self):
        for status in ("running", "interrupted", "verification_failed"):
            with self.subTest(status=status):
                self.runs.list_read_only.return_value = []
                self.add_run(status)
                self.assertEqual(self.service.load().cta("system").action, "recovery")

    def test_missing_pending_plan_goes_to_review_not_update(self):
        self.add_run("awaiting_reboot")
        self.plans.list_read_only.return_value = []
        state = self.service.load().source("system")
        self.assertEqual(update_cta(state).action, "recovery")
        self.assertFalse(state.reboot_required)

    def test_corrupt_action_history_is_an_error_not_an_empty_result(self):
        self.runs.list_read_only.side_effect = ValueError("corrupt")
        state = self.service.load()
        for item in state.sources:
            self.assertEqual(item.status, "error")
            self.assertEqual(update_cta(item).action, "recovery")
            self.assertEqual(item.run_id, "")

    def test_semantically_corrupt_history_is_a_read_error(self):
        for status, stamp in (("bogus", 100), ("succeeded", float("nan")), ("failed", float("inf")), ("failed", 1e30)):
            with self.subTest(state=status, timestamp=stamp):
                self.runs.list_read_only.return_value = []
                self.add_run(status, timestamp=stamp)
                result = self.service.load().source("system")
                self.assertEqual(result.status, "error")
                self.assertEqual(result.run_id, "")
                self.assertEqual(update_cta(result).action, "recovery")

    def test_corrupt_observation_cache_is_reported(self):
        self.overview.load.return_value = UpdateOverviewSnapshot(storage_status="unavailable")
        self.assertEqual(self.service.load().source("firmware").status, "error")

    def test_a_newer_explicit_check_supersedes_old_terminal_history(self):
        self.add_run("failed")
        checked_at = datetime.fromtimestamp(200, timezone.utc).isoformat()
        self.overview.load.return_value = UpdateOverviewSnapshot(sources=(
            UpdateSourceResult("system", "available", checked_at, (UpdateItem("example"),), stale=False),
            UpdateSourceResult("flatpak"), UpdateSourceResult("firmware"),
        ))
        state = self.service.load().source("system")
        self.assertEqual(update_cta(state).action, "update")
        self.assertEqual(state.run_id, "")

    def test_snapshot_candidates_include_versions_timestamp_retention_and_omitted_count(self):
        from core.tasks.update_flow import MAX_VISIBLE_UPDATE_DETAILS
        from services.software.update_overview import UpdateItem

        checked_at = datetime.fromtimestamp(200, timezone.utc).isoformat()
        items = tuple(
            UpdateItem(f"package-{index}", old_version="1.0", version="2.0")
            for index in range(MAX_VISIBLE_UPDATE_DETAILS + 3)
        )
        self.overview.load.return_value = UpdateOverviewSnapshot(sources=(
            UpdateSourceResult(
                "system", "available", checked_at, items,
                stale=True, items_retained=True,
            ),
            UpdateSourceResult("flatpak"),
            UpdateSourceResult("firmware"),
        ))

        result = self.service.load().source("system")

        self.assertEqual(result.checked_at, checked_at)
        self.assertTrue(result.stale)
        self.assertEqual(result.item_count, MAX_VISIBLE_UPDATE_DETAILS + 3)
        self.assertIn("Previously observed candidates", result.details[0])
        self.assertIn("package-0 · 1.0 → 2.0", result.details[1])
        self.assertIn("3 additional updates are not shown", result.details[-1])
        self.assertEqual(len(result.details), MAX_VISIBLE_UPDATE_DETAILS + 2)


class TestRecoveredUpdatesPresentation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from ui.update_workflow import UpdateWorkflowPage
        self.page = UpdateWorkflowPage(service=Mock())
        self.addCleanup(self.page.close)

    def test_checking_one_source_does_not_drop_pending_other_run(self):
        self.page.set_source(UpdateSourceState("firmware", "awaiting_reboot", run_id="saved", stale=False))
        self.page._checking_source = "system"
        self.page.set_snapshot(UpdateOverviewSnapshot())
        self.assertEqual(self.page.source_state("firmware").run_id, "saved")
        self.assertEqual(self.page.source_button("firmware").text(), "Continue")

    def test_hydration_disables_buttons_and_restores_saved_result(self):
        self.page.set_loading(True)
        self.assertFalse(self.page.source_button("system").isEnabled())
        state = UpdateOverviewState().replace_source(UpdateSourceState("system", "verifying", run_id="saved", stale=False))
        self.page.restore_saved_state(state)
        self.page.set_loading(False)
        self.assertEqual(self.page.source_button("system").text(), "Verify")
        self.assertTrue(self.page.source_button("system").isEnabled())

    def test_failed_verification_offers_review_and_deliberate_new_check(self):
        self.page.apply_outcome("firmware", SimpleNamespace(status="verification_failed", run_id="saved", message="Failed"))
        self.assertEqual(self.page.source_button("firmware").text(), "Review")
        self.assertFalse(self.page._check_again_buttons["firmware"].isHidden())
