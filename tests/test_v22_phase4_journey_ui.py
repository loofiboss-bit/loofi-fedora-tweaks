"""Static contract for the V22 accessibility journey matrix."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "validate_v22_phase4_journey_ui.py"


def _load_validator():
    spec = importlib.util.spec_from_file_location("v22_phase4_journey_ui", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestV22Phase4JourneyUiContract(unittest.TestCase):
    def test_matrix_covers_each_surface_and_required_axis(self) -> None:
        validator = _load_validator()
        matrix = validator.build_matrix()

        self.assertEqual(len(matrix), 16)
        self.assertEqual({case.surface for case in matrix}, {"home", "system_check", "action_center", "activity"})
        self.assertEqual({case.viewport for case in matrix}, {(1366, 768), (860, 560)})
        self.assertEqual({case.direction for case in matrix}, {"ltr", "rtl"})
        self.assertEqual(validator.THEME, "highcontrast")
        self.assertEqual((validator.BASE_POINT_SIZE, validator.SCALE_PERCENT), (14, 200))
        self.assertTrue(validator.REDUCED_MOTION)

    def test_static_contract_passes_without_claiming_physical_accessibility(self) -> None:
        validator = _load_validator()
        self.assertEqual(validator.validate_static_contract(), [])


if __name__ == "__main__":
    unittest.main()
