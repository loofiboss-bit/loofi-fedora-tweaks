"""Release-gate coverage for the canonical System Check contract."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "validate_system_check_contract.py"
)


def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_system_check_contract",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("System Check validator could not be loaded.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestSystemCheckReleaseGate(unittest.TestCase):
    def test_current_contract_passes(self):
        self.assertEqual(_load_validator().validate(), [])

    def test_cli_reports_success(self):
        self.assertEqual(_load_validator().main(), 0)


if __name__ == "__main__":
    unittest.main()
