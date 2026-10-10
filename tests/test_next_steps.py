"""Suggestions preserve observation provenance and never initiate checks."""
import unittest
from types import SimpleNamespace

from core.tasks.next_steps import next_steps


class TestNextSteps(unittest.TestCase):
    def setUp(self):
        self.now = 100000.0
        self.maintenance = {"health": {"status": "completed", "sampled_at": self.now, "findings": []},
                            "updates": {"status": "ok", "sources": [{"status": "up_to_date", "stale": False,
                                                                         "sampled_at": self.now, "count": 0}]}}

    def test_priorities_and_limit(self):
        self.maintenance["activity"] = {"runs": [{"status": "failed", "action_id": "tweak", "sampled_at": self.now},
                                                  {"status": "awaiting_reboot", "action_id": "update-fedora-system", "sampled_at": self.now}]}
        self.maintenance["health"]["findings"] = [{"severity": "critical", "freshness_state": "fresh", "summary": "Disk"}]
        self.maintenance["updates"]["sources"][0].update(status="available", count=2)
        result = next_steps(self.maintenance, now=self.now)
        self.assertEqual([step.id for step in result], ["pending", "failed", "health"])
        self.assertEqual(result[0].route, "maintenance:updates")
        self.assertEqual(result[0].sampled_at, self.now)

    def test_old_failed_action_survives_new_success(self):
        self.maintenance["activity"] = {"status": "succeeded", "runs": [{"status": "failed", "sampled_at": 1},
                                                                          {"status": "succeeded", "sampled_at": self.now}]}
        self.assertEqual(next_steps(self.maintenance, now=self.now)[0].id, "failed")

    def test_missing_stale_and_corrupt_produce_checks(self):
        self.assertEqual([step.id for step in next_steps({}, now=self.now)], ["health-check", "update-check"])
        self.maintenance["health"]["sampled_at"] = 1
        self.maintenance["updates"]["sources"][0].update(status="available", count=3, stale=True)
        self.assertEqual([step.id for step in next_steps(self.maintenance, now=self.now)], ["health-check", "update-check"])
        self.maintenance["activity"] = {"status": "error", "detail": "Unreadable"}
        self.assertEqual(next_steps(self.maintenance, now=self.now)[0].id, "history-error")

    def test_unknown_freshness_and_future_timestamp_need_check(self):
        self.maintenance["health"].update(sampled_at=self.now + 100,
                                          findings=[{"severity": "critical", "freshness_state": "unknown"}])
        self.assertEqual(next_steps(self.maintenance, now=self.now)[0].id, "health-check")

    def test_critical_storage_uses_existing_root_threshold_only(self):
        metric = SimpleNamespace(id="storage:/", status="ready", value=95, sampled_at=self.now)
        self.assertEqual(next_steps(self.maintenance, (metric,), now=self.now)[0].id, "health")
        metric.value = 94
        self.assertEqual(next_steps(self.maintenance, (metric,), now=self.now), ())
        metric.value = 99
        metric.status = "stale"
        self.assertEqual(next_steps(self.maintenance, (metric,), now=self.now), ())

    def test_only_fresh_available_updates_are_suggested(self):
        self.maintenance["updates"]["sources"][0].update(status="available", count=3)
        self.assertEqual(next_steps(self.maintenance, now=self.now)[0].id, "updates")
        self.maintenance["updates"]["status"] = "error"
        self.assertEqual(next_steps(self.maintenance, now=self.now)[0].id, "update-check")

    def test_available_updates_precede_missing_health_check(self):
        self.maintenance.pop("health")
        self.maintenance["updates"]["sources"][0].update(status="available", count=2)
        self.assertEqual([step.id for step in next_steps(self.maintenance, now=self.now)], ["updates", "health-check"])

    def test_failed_update_retains_exact_source_and_run(self):
        self.maintenance["activity"] = {"runs": [{"status": "failed", "action_id": "update-flatpaks", "run_id": "exact-run", "sampled_at": self.now}]}
        step = next_steps(self.maintenance, now=self.now)[0]
        self.assertEqual(step.route, "health")
        self.assertEqual(step.context.to_dict(), {"run_id": "exact-run", "update_source": "flatpak"})

    def test_pending_and_generic_failure_preserve_run_identity(self):
        self.maintenance["activity"] = {"runs": [{"status": "awaiting_reboot", "action_id": "update-fedora-system", "run_id": "pending-run", "sampled_at": self.now},
                                                  {"status": "failed", "action_id": "tweak", "run_id": "failed-run", "sampled_at": self.now}]}
        steps = next_steps(self.maintenance, now=self.now)
        self.assertEqual(steps[0].context.to_dict(), {"run_id": "pending-run", "update_source": "system"})
        self.assertEqual(steps[1].context.to_dict(), {"run_id": "failed-run"})

    def test_storage_metric_preselects_symptom_without_collecting(self):
        metric = SimpleNamespace(id="storage:/", status="ready", value=96, sampled_at=self.now)
        step = next_steps(self.maintenance, (metric,), now=self.now)[0]
        self.assertEqual(step.context.to_dict(), {"symptom": "storage_full"})
