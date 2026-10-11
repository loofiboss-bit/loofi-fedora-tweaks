"""Deterministic evidence boundaries and safe offscreen UX measurements."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "measure_ux_baseline.py"
SPEC = importlib.util.spec_from_file_location("ux_baseline", SCRIPT)
baseline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(baseline)


class TestUxBaselineCalculations(unittest.TestCase):
    def test_percentile_preserves_nearest_rank_and_raw_samples(self):
        result = baseline._summary([4.0, 1.0, 3.0, 2.0])
        self.assertEqual(result, {"samples_ms": [4.0, 1.0, 3.0, 2.0], "p50_ms": 2.5, "p95_ms": 4.0, "max_ms": 4.0})
        self.assertEqual(baseline._percentile([0.2], 0.95), 0.2)

    @patch.object(baseline, "_run_startup_child")
    def test_process_pairs_alternate_control_order_without_reordering_pairs(self, child):
        # Pair two runs current/control; pairing must preserve the candidate delta.
        child.side_effect = [(20.0, {}), (30.0, {}), (45.0, {}), (30.0, {})]
        result = baseline.measure_startup_pairs(3, 2)
        self.assertEqual(result["alternating_order"], [["qt_bootstrap", "current_shell"], ["current_shell", "qt_bootstrap"]])
        self.assertEqual(result["paired_current_minus_control_ms"]["samples_ms"], [10.0, 15.0])
        self.assertEqual([call.args[0] for call in child.call_args_list], ["qt", "shell", "shell", "qt"])
        self.assertIsNone(result["baseline_revision"])
        self.assertEqual(result["comparison_metric"], "process lifecycle wall time")

    @patch.object(baseline, "_isolated_environment", return_value={"QT_QPA_PLATFORM": "offscreen"})
    @patch.object(baseline.subprocess, "run")
    def test_startup_child_is_bounded_and_respects_reference_source(self, run, _environment):
        run.return_value = Mock(stdout='{"ready": true, "measurements": {}}')
        elapsed, report = baseline._run_startup_child("shell", 3, Path("/fixture/reference"))
        self.assertGreaterEqual(elapsed, 0)
        self.assertTrue(report["ready"])
        arguments = run.call_args.kwargs
        self.assertEqual(arguments["timeout"], 60)
        self.assertTrue(arguments["check"])
        self.assertEqual(arguments["env"]["PYTHONPATH"], "/fixture/reference")
        self.assertNotIn("shell", arguments)

    @patch.object(baseline, "_isolated_environment", return_value={})
    @patch.object(baseline.subprocess, "run")
    def test_startup_without_ready_evidence_is_rejected(self, run, _environment):
        run.return_value = Mock(stdout='{"ready": false}')
        with self.assertRaisesRegex(RuntimeError, "did not report ready"):
            baseline._run_startup_child("qt", 3)


class TestUxBaselineStateIsolation(unittest.TestCase):
    def test_explicit_xdg_fixture_blocks_legacy_home_settings_inheritance(self):
        with TemporaryDirectory(prefix="loofi-ux-isolation-test-") as directory:
            legacy_home = Path(directory) / "legacy-home"
            legacy_config = legacy_home / ".config" / "loofi-fedora-tweaks"
            legacy_config.mkdir(parents=True)
            legacy_file = legacy_config / "settings.json"
            legacy_text = json.dumps({"theme": "highcontrast", "restore_last_tab": True,
                                      "last_route_id": "maintenance:updates", "overview_intro_dismissed": True})
            legacy_file.write_text(legacy_text, encoding="utf-8")
            private = Path(directory) / "private-xdg"
            private.mkdir()
            env = baseline._isolated_environment(str(private))
            # This HOME exists only in the child fixture; the parent's environment
            # and the maintainer's real settings are not changed.
            env["HOME"] = str(legacy_home)
            result = subprocess.run(
                [sys.executable, "-c", "import json; from utils.settings import SettingsManager; "
                 "from utils.log import get_logger; get_logger('ux_fixture').info('fixture'); "
                 "s=SettingsManager.instance(); print(json.dumps({k:s.get(k) for k in "
                 "('theme','restore_last_tab','last_route_id','overview_intro_dismissed')}))"],
                cwd=ROOT, env=env, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), {"theme": "dark", "restore_last_tab": False,
                                                         "last_route_id": "overview", "overview_intro_dismissed": False})
            self.assertEqual(legacy_file.read_text(encoding="utf-8"), legacy_text)
            self.assertEqual(Path(env["XDG_STATE_HOME"]), private / "state")
            self.assertTrue((private / "state" / "loofi-fedora-tweaks" / "app.log").is_file())
            self.assertFalse((legacy_home / ".local" / "state").exists())


class TestUxBaselineOffscreenIntegration(unittest.TestCase):
    def run_fixture(self, *arguments):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *arguments], cwd=ROOT,
            env=dict(os.environ, PYTHONPATH=str(ROOT / "loofi-fedora-tweaks"), QT_QPA_PLATFORM="offscreen"),
            capture_output=True, text=True, timeout=30,
        )

    def test_real_widget_workflows_have_observed_counts_and_declared_limits(self):
        result = self.run_fixture("--rows", "3", "--catalog-sizes", "2,3", "--samples", "2", "--startup-pairs", "0")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["fixture"]["catalog_rows"], 3)
        self.assertEqual(report["additional_catalogs"][0]["fixture"]["catalog_rows"], 2)
        self.assertEqual(report["process_startup"], {"status": "not requested"})
        expected_counts = {
            "apps_search_select_review": 3,
            "apps_view_roundtrip": 2,
            "overview_intro_roundtrip": 2,
            "tweak_search_change_restore": 3,
            "profile_review_acceptance": 1,
            "flatpak_removal_review": 1,
            "rpm_handoff_return_refresh": 2,
        }
        for name, count in expected_counts.items():
            with self.subTest(workflow=name):
                workflow = report["workflows"][name]
                self.assertEqual(workflow["input_actions"], count)
                self.assertEqual(len(workflow["observed_actions"]), count)
                self.assertTrue(workflow["scope"])
        self.assertIn("injected", report["workflows"]["tweak_search_change_restore"]["scope"])
        self.assertIn("mocked", report["workflows"]["rpm_handoff_return_refresh"]["scope"])
        self.assertEqual(set(report["measured_ms"]["first_existing_page_open"]), {"apps", "overview"})
        self.assertTrue(report["limits"])
        self.assertEqual(report["environment"]["qt_platform"], "offscreen")

    def test_original_single_search_sample_option_remains_supported(self):
        result = self.run_fixture("--rows", "1", "--catalog-sizes", "1", "--samples", "1", "--startup-pairs", "0")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["fixture"]["search_samples"], 1)
        self.assertEqual(report["fixture"]["navigation_samples"], 2)
        self.assertEqual(set(report["measured_ms"]["first_existing_page_open"]), {"apps", "overview"})

    def test_shell_measurement_is_explicitly_separate_from_system_collection(self):
        result = self.run_fixture("--startup-child", "shell")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["ready"])
        self.assertEqual(report["measurements"]["system_collection"], "disabled: mocked dashboard and tweak snapshot")
        self.assertGreater(report["measurements"]["import_qt_shell_first_event_pump_ms"], 0)
        self.assertEqual(len(report["measurements"]["warm_route_hops"]["samples_ms"]), 16)

    def test_invalid_inputs_fail_before_gui_or_measurements(self):
        for arguments in (("--rows", "0"), ("--samples", "0"), ("--catalog-sizes", "bad"), ("--startup-pairs", "-1")):
            with self.subTest(arguments=arguments):
                result = self.run_fixture(*arguments)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
