"""Static contracts for the Resolve Phase 3 real-shell validation matrix."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "validate_v21_phase3_ui.py"


def _load_validator():
    spec = importlib.util.spec_from_file_location("v21_phase3_validator", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestV21Phase3ValidationContract(unittest.TestCase):
    def test_matrix_covers_exact_phase3_axes(self) -> None:
        validator = _load_validator()
        matrix = validator.build_matrix()

        self.assertEqual(len(matrix), 256)
        self.assertEqual({case.theme for case in matrix}, set(validator.THEMES))
        self.assertEqual(
            {case.viewport for case in matrix},
            {(860, 560), (900, 720), (1366, 768), (1920, 1080)},
        )
        self.assertEqual(
            {case.scale_percent for case in matrix},
            {100, 125, 150, 200},
        )
        self.assertEqual({case.direction for case in matrix}, {"ltr", "rtl"})
        self.assertEqual(
            {case.route_id for case in matrix},
            {"settings", "development"},
        )

    def test_static_contract_inherits_accessibility_and_contrast_gates(self) -> None:
        validator = _load_validator()
        self.assertEqual(validator.validate_static_contract(), [])


if __name__ == "__main__":
    unittest.main()
