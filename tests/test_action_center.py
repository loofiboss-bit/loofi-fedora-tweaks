"""Tests for v11 Harbor Action Center primitives."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))

from core.actions import ActionCenterService, ActionHistoryStore, ActionQueue, RollbackGuidanceService
from core.diagnostics.readiness_actions import ReadinessActionCandidate
from core.executor.action_result import ActionResult


def _candidate(risk_level="medium", manual_only=False):
    return ReadinessActionCandidate(
        id="test-action",
        title="Test Action",
        explanation="Preview this action.",
        related_check_id="repo-health",
        command_preview=["pkexec", "dnf5", "clean", "all"],
        risk_level=risk_level,
        privileged=True,
        manual_only=manual_only,
        revert_hint="Re-run repository checks after the cache rebuilds.",
        verification_command=["dnf5", "repolist", "--enabled"],
        command="dnf5",
        args=["clean", "all"],
    )


class TestActionCenterService(unittest.TestCase):
    """Action Center stays policy-backed and rootless under tests."""

    def test_from_readiness_candidate_adds_rollback_and_state(self):
        with patch("core.actions.rollback.SystemManager.is_atomic", return_value=True):
            item = ActionCenterService().from_readiness_candidate(_candidate(), target="45-preview")

        self.assertEqual(item.source, "readiness:45-preview")
        self.assertEqual(item.risk_level, "medium")
        self.assertTrue(item.confirmation_required)
        self.assertEqual(item.privilege, "pkexec")
        self.assertEqual(item.rollback_guidance.mechanism, "rpm-ostree")

    def test_preview_uses_facade_without_execution(self):
        facade = MagicMock()
        facade.preview.return_value = ActionResult.previewed("pkexec", ["dnf5", "clean", "all"], action_id="test-action")
        service = ActionCenterService(facade=facade)
        item = service.from_readiness_candidate(_candidate(risk_level="low"))

        result = service.preview(item)

        self.assertTrue(result.preview)
        self.assertIn("action_center", result.data)
        facade.preview.assert_called_once_with(["pkexec", "dnf5", "clean", "all"], privileged=False, action_id="test-action")

    def test_manual_only_preview_does_not_call_facade(self):
        facade = MagicMock()
        service = ActionCenterService(facade=facade)
        item = service.from_readiness_candidate(_candidate(manual_only=True))

        result = service.preview(item)

        self.assertTrue(result.success)
        self.assertTrue(result.preview)
        facade.preview.assert_not_called()

    def test_preview_rejects_item_without_command_preview(self):
        facade = MagicMock()
        service = ActionCenterService(facade=facade)
        item = service.from_readiness_candidate(_candidate(risk_level="low"))
        item.command_preview = []

        result = service.preview(item)

        self.assertFalse(result.success)
        self.assertIn("no command preview", result.message.lower())
        facade.preview.assert_not_called()

    def test_queue_blocks_medium_risk_without_confirmation(self):
        facade = MagicMock()
        history = ActionHistoryStore(Path(tempfile.mkdtemp()) / "history.jsonl")
        service = ActionCenterService(facade=facade, history=history, queue=ActionQueue())
        item = service.from_readiness_candidate(_candidate())
        item.confirmation_required = True
        item.state = "ready"
        service.enqueue([item])

        result = service.execute_next(confirmed=False)

        self.assertFalse(result.success)
        self.assertIn("confirmation", result.message.lower())
        facade.execute.assert_not_called()

    def test_execute_next_without_ready_item_fails(self):
        service = ActionCenterService(facade=MagicMock(), queue=ActionQueue())

        result = service.execute_next()

        self.assertFalse(result.success)
        self.assertIn("no ready action", result.message.lower())

    def test_execute_next_blocks_missing_command_preview(self):
        facade = MagicMock()
        service = ActionCenterService(facade=facade, queue=ActionQueue())
        item = service.from_readiness_candidate(_candidate(risk_level="low"))
        item.state = "ready"
        service.enqueue([item])
        item.command_preview = []

        result = service.execute_next()

        self.assertFalse(result.success)
        self.assertIn("no command preview", result.message.lower())
        facade.execute.assert_not_called()

    def test_execute_next_records_successful_execution(self):
        facade = MagicMock()
        facade.execute.return_value = ActionResult.ok("done", action_id="test-action")
        history = ActionHistoryStore(Path(tempfile.mkdtemp()) / "history.jsonl")
        service = ActionCenterService(facade=facade, history=history, queue=ActionQueue())
        item = service.from_readiness_candidate(_candidate(risk_level="low"))
        item.state = "ready"
        service.enqueue([item])

        result = service.execute_next(timeout=5)

        self.assertTrue(result.success)
        self.assertIn("action_center", result.data)
        facade.execute.assert_called_once_with(["pkexec", "dnf5", "clean", "all"], privileged=False, timeout=5, action_id="test-action")
        self.assertEqual(history.recent()[-1]["event"], "executed")

    def test_history_store_is_bounded_and_readable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ActionHistoryStore(Path(tmpdir) / "history.jsonl")
            store.append({"event": "queued", "id": "one"})

            self.assertEqual(store.recent(), [{"event": "queued", "id": "one"}])


class TestRollbackGuidanceService(unittest.TestCase):
    """Rollback guidance covers Atomic and manual fallback paths."""

    @patch("core.actions.rollback.SystemManager.is_atomic", return_value=True)
    def test_atomic_uses_rpm_ostree_guidance(self, _mock_atomic):
        guidance = RollbackGuidanceService.guidance_for("high")
        self.assertEqual(guidance.mechanism, "rpm-ostree")
        self.assertEqual(guidance.command_preview, ["rpm-ostree", "rollback"])

    @patch("core.actions.rollback.shutil.which", return_value=None)
    @patch("core.actions.rollback.SystemManager.is_atomic", return_value=False)
    def test_traditional_without_snapshot_uses_manual_guidance(self, _mock_atomic, _mock_which):
        guidance = RollbackGuidanceService.guidance_for("medium", "Manual recovery only.")
        self.assertEqual(guidance.mechanism, "manual")
        self.assertFalse(guidance.supported)


if __name__ == "__main__":
    unittest.main()
