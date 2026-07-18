"""Tests for the non-mutating Phase 6 manual validation script."""

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "validate_v15_phase6_workflows.py"


def _load_validator():
    spec = importlib.util.spec_from_file_location("phase6_validator", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TestPhase6Validator(unittest.TestCase):
    def test_contract_validation_passes_without_host_probe(self):
        self.assertEqual(_load_validator().validate(), [])

    def test_json_cli_reports_five_workflows_and_zero_mutations(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--json"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )

        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(payload["workflows"]), 5)
        self.assertEqual(payload["host_probes"], 0)
        self.assertEqual(payload["mutations"], 0)
        self.assertEqual(payload["status"], "passed")


if __name__ == "__main__":
    unittest.main()
