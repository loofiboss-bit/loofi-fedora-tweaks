"""PyQt-free GuidedTask composition contracts."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from core.home.models import GuidedTask, Recommendation
from core.home.service import HomeService


class TestGuidedTask(unittest.TestCase):
    def test_model_is_inert_and_requires_existing_identifiers(self):
        task = GuidedTask(
            "review-run",
            "run",
            "Review maintenance",
            "A saved run needs review.",
            "maintenance:action-center",
            "run-1",
        )

        self.assertEqual(task.source_id, "run-1")
        self.assertFalse(hasattr(task, "command"))
        self.assertFalse(hasattr(task, "callback"))
        with self.assertRaises(ValueError):
            GuidedTask("invalid", "route", "Title", "Summary", "", "")

    def test_primary_run_and_active_work_use_existing_run_ids(self):
        recommendation = Recommendation(
            "run-review",
            "action_run_review",
            "Review maintenance",
            "An interrupted run needs review.",
            "maintenance:action-center",
            "critical",
        )
        failed = SimpleNamespace(
            run_id="run-failed",
            state="interrupted",
            updated_at=20.0,
            reboot_required=False,
        )
        running = SimpleNamespace(
            run_id="run-running",
            state="running",
            updated_at=10.0,
            reboot_required=False,
        )

        primary = HomeService._guided_primary_task(
            recommendation,
            now=30.0,
            latest=None,
            plans=(),
            runs=(running, failed),
        )
        active = HomeService._active_work_task((running, failed), primary)

        self.assertIsNotNone(primary)
        self.assertEqual(primary.source_id, "run-failed")
        self.assertIsNotNone(active)
        self.assertEqual(active.source_id, "run-running")

    def test_system_check_task_binds_saved_check_id(self):
        recommendation = Recommendation(
            "partial",
            "system_check_partial",
            "Some checks were unavailable",
            "Review the saved partial result.",
            "maintenance:health-timeline",
        )
        snapshot = SimpleNamespace(
            daily_maintenance={"system_check": {"check_id": "check-1"}}
        )

        task = HomeService._guided_primary_task(
            recommendation,
            now=30.0,
            latest=snapshot,
            plans=(),
            runs=(),
        )

        self.assertEqual(task.source, "system_check")
        self.assertEqual(task.source_id, "check-1")


if __name__ == "__main__":
    unittest.main()
