"""Smoke test for the stable Phase 2 startup benchmark contract."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class TestStartupBenchmark(unittest.TestCase):
    def test_clean_process_home_marker_has_no_specialist_runtime(self):
        root = Path(__file__).parents[1]
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "startup.json"
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(root / "loofi-fedora-tweaks")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(root / "scripts" / "benchmark_startup.py"),
                    "--warmups",
                    "0",
                    "--runs",
                    "1",
                    "--output",
                    str(output),
                ],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
                timeout=30,
            )

            payload = json.loads(output.read_text())

        self.assertEqual(completed.returncode, 0)
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["method"]["marker"], "AtlasDashboardTab realized")
        run = payload["runs"][0]
        self.assertEqual(run["runtime_plugin_ids"], ["atlas_dashboard"])
        self.assertEqual(run["plugin_spec_count"], 28)
        self.assertEqual(run["installed_components"], ["core", "specialist"])
        self.assertEqual(run["running_qthreads"], 0)
        self.assertEqual(run["subprocess_probes"], [])
        self.assertNotIn("ui.dashboard_tab", run["imports"]["ui_modules"])
        specialist = {
            "ui.agents_tab",
            "ui.ai_enhanced_tab",
            "ui.community_tab",
            "ui.performance_tab",
            "ui.virtualization_tab",
        }
        self.assertTrue(specialist.isdisjoint(run["imports"]["ui_modules"]))


if __name__ == "__main__":
    unittest.main()
