"""Regression contracts for shared formatters and Action Center helpers."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "loofi-fedora-tweaks"))

from core.actions import assurance, continuity_recovery
from core.actions.public_boundary_definitions import _manual_definition as boundary_definition
from core.export.kickstart import KickstartGenerator
from core.executor.action_result import ActionResult
from services.network.monitor import NetworkMonitor
from services.system.processes import ProcessManager
from utils.formatting import bytes_to_legacy_human
from utils.monitor import SystemMonitor
from utils.performance import PerformanceCollector
from utils.software_utils import parse_flatpak_application_list


class TestSharedActionHelpers(unittest.TestCase):
    def test_assurance_and_boundary_keep_their_denial_policy(self):
        assurance_definition = assurance._manual_definition(
            "test-assurance",
            "Test",
            "Description",
            "Recovery",
            ("test-resource",),
        )
        boundary = boundary_definition(
            "test-boundary",
            "Test",
            "Description",
            "Recovery",
            ("test-resource",),
        )

        assurance_decision = assurance_definition.preflight_checker({}, None)
        boundary_decision = boundary.preflight_checker({}, None)
        self.assertFalse(assurance_decision.allowed)
        self.assertEqual(assurance_decision.alternative, "Review the current state and create a fresh plan.")
        self.assertFalse(boundary_decision.allowed)
        self.assertEqual(boundary_decision.alternative, "")

    def test_action_helper_import_paths_share_one_implementation(self):
        self.assertIs(assurance._json_payload, continuity_recovery._json_payload)
        self.assertIs(assurance._pending_deployment, continuity_recovery._pending_deployment)
        self.assertIs(assurance._runtime_boot_id, continuity_recovery._runtime_boot_id)

    def test_shared_json_parser_keeps_failure_and_list_shapes(self):
        self.assertIsNone(assurance._json_payload(ActionResult.fail("failed")))
        self.assertIsNone(assurance._json_payload(ActionResult.ok("invalid", stdout="{")))
        self.assertEqual(assurance._json_payload(ActionResult.ok("list", stdout='["a", "b"]')), {"items": ["a", "b"]})
        self.assertEqual(assurance._json_payload(ActionResult.ok("object", stdout='{"ready": true}')), {"ready": True})

    def test_pending_deployment_prefers_staged_and_ignores_booted(self):
        staged = {"staged": True, "checksum": "staged"}
        pending = {"pending": True, "checksum": "pending"}
        booted = {"staged": True, "booted": True, "checksum": "booted"}
        self.assertIs(assurance._pending_deployment([pending, staged]), staged)
        self.assertIs(assurance._pending_deployment([booted, pending]), pending)
        self.assertEqual(assurance._pending_deployment({"deployments": [pending]}), {})


class TestSharedFormatting(unittest.TestCase):
    def test_monitor_wrappers_keep_legacy_labels_and_boundaries(self):
        formatters = (
            NetworkMonitor.bytes_to_human,
            ProcessManager.bytes_to_human,
            SystemMonitor.bytes_to_human,
            PerformanceCollector.bytes_to_human,
        )
        for value, expected in (
            (0, "0.0 B"),
            (1023, "1023.0 B"),
            (1024, "1.0 KB"),
            (1024**3, "1.0 GB"),
            (1024**5, "1.0 PB"),
            (-1024, "-1.0 KB"),
        ):
            with self.subTest(value=value):
                self.assertEqual(bytes_to_legacy_human(value), expected)
                for formatter in formatters:
                    self.assertEqual(formatter(value), expected)

    def test_flatpak_listing_parser_trims_and_discards_empty_lines(self):
        self.assertEqual(
            parse_flatpak_application_list("\n org.example.App \n\norg.example.Other\n"),
            ["org.example.App", "org.example.Other"],
        )
        self.assertEqual(parse_flatpak_application_list("\n  \n"), [])

    @patch("core.export.kickstart.cached_which", return_value="/usr/bin/flatpak")
    @patch("core.export.kickstart.subprocess.run")
    def test_kickstart_export_uses_shared_flatpak_parser(self, run, _which):
        run.return_value = SimpleNamespace(returncode=0, stdout="org.example.App\n\n")
        self.assertEqual(KickstartGenerator._get_flatpak_apps(), ["org.example.App"])
        run.assert_called_once_with(
            ["flatpak", "list", "--app", "--columns=application"],
            capture_output=True,
            text=True,
            timeout=30,
        )


if __name__ == "__main__":
    unittest.main()
