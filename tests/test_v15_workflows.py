"""Tests for Phase 6's PyQt-free workflow contracts."""

import subprocess
import unittest
from unittest.mock import patch

from core.workflows import (
    CORE_WORKFLOWS,
    ReclaimAnalysisService,
    SlowSystemService,
    SlowSystemSnapshot,
    workflow_definition,
)
from services.storage.reclaim import ReclaimProbeService, _parse_human_size


class TestWorkflowDefinitions(unittest.TestCase):
    def test_five_workflows_have_one_preferred_compatible_route(self):
        self.assertEqual(len(CORE_WORKFLOWS), 5)
        self.assertEqual(
            [workflow.preferred_route_id for workflow in CORE_WORKFLOWS],
            [
                "maintenance:updates",
                "software:apps",
                "system-monitor:performance",
                "maintenance:cleanup",
                "snapshots",
            ],
        )
        self.assertEqual(workflow_definition("free-disk-space").title, "Free disk space")


class TestSlowSystemService(unittest.TestCase):
    def test_storage_pressure_has_priority_and_never_creates_an_action(self):
        snapshot = SlowSystemSnapshot(92, 90, 96, 30, failed_services=("broken.service",))

        summary = SlowSystemService.summarize(snapshot)

        self.assertEqual(summary.state, "critical")
        self.assertEqual(summary.bottleneck, "Storage pressure")
        self.assertEqual(summary.action_center_link.action_id, "restart-failed-service")
        self.assertEqual(summary.action_center_link.parameters, {"service": "broken.service"})

    def test_failed_service_link_requires_an_exact_systemd_unit(self):
        summary = SlowSystemService.summarize(
            SlowSystemSnapshot(10, 20, 30, 0, failed_services=("bad;unit", "safe.timer"))
        )

        self.assertEqual(summary.bottleneck, "Failed service")
        self.assertEqual(summary.action_center_link.parameters["service"], "safe.timer")

    def test_missing_metrics_returns_unknown_without_mutation_handoff(self):
        summary = SlowSystemService.summarize(SlowSystemSnapshot(None, None, None, None))

        self.assertEqual(summary.state, "unknown")
        self.assertIsNone(summary.action_center_link)

    def test_injected_collector_is_used_once(self):
        calls = []
        service = SlowSystemService(lambda: calls.append("collect") or SlowSystemSnapshot(5, 10, 20, 0))

        summary = service.collect()

        self.assertEqual(calls, ["collect"])
        self.assertEqual(summary.state, "good")


class TestReclaimAnalysis(unittest.TestCase):
    def test_traditional_cache_and_trim_route_only_to_v14_definitions(self):
        analysis = ReclaimAnalysisService.build(
            atomic=False,
            package_cache_bytes=4096,
            journal_bytes=2048,
        )

        links = [category.action_center_link for category in analysis.categories if category.action_center_link]
        self.assertEqual({link.action_id for link in links}, {"dnf-clean-all", "fstrim-all"})
        self.assertEqual(analysis.estimated_selected_bytes, 4096)
        self.assertFalse(analysis.categories[0].manual_only)

    def test_atomic_package_cache_is_fail_closed_and_manual_only(self):
        analysis = ReclaimAnalysisService.build(
            atomic=True,
            package_cache_bytes=999,
            journal_bytes=None,
        )

        cache = analysis.categories[0]
        self.assertTrue(cache.manual_only)
        self.assertFalse(cache.selected_by_default)
        self.assertIsNone(cache.action_center_link)
        self.assertIn("rpm-ostree", cache.guidance)

    def test_probe_uses_read_only_timeout_bounded_commands(self):
        commands = []

        def runner(command, timeout):
            commands.append((command, timeout))
            if command[0] == "du":
                return subprocess.CompletedProcess(command, 1, "100\t/var/cache/dnf\n200\t/var/cache/libdnf5\n", "")
            return subprocess.CompletedProcess(command, 0, "Archived and active journals take up 1.5G in the file system.\n", "")

        with patch("services.storage.reclaim.SystemManager.is_atomic", return_value=False):
            analysis = ReclaimProbeService(runner).analyze()

        self.assertEqual(commands, [
            (["du", "-sb", "/var/cache/dnf", "/var/cache/libdnf5"], 10),
            (["journalctl", "--disk-usage", "--no-pager"], 10),
        ])
        self.assertEqual(analysis.categories[0].estimated_bytes, 300)
        self.assertEqual(analysis.categories[1].estimated_bytes, int(1.5 * 1024**3))

    def test_atomic_probe_skips_dnf_cache_path(self):
        commands = []

        def runner(command, timeout):
            commands.append((command, timeout))
            return subprocess.CompletedProcess(command, 0, "0B", "")

        with patch("services.storage.reclaim.SystemManager.is_atomic", return_value=True):
            ReclaimProbeService(runner).analyze()

        self.assertEqual(commands, [(["journalctl", "--disk-usage", "--no-pager"], 10)])

    def test_human_size_parser_is_bounded_and_explicit(self):
        self.assertEqual(_parse_human_size("take up 512.0M"), 512 * 1024**2)
        self.assertEqual(_parse_human_size("take up 2 GB"), 2 * 1024**3)
        self.assertIsNone(_parse_human_size("unknown"))


if __name__ == "__main__":
    unittest.main()
