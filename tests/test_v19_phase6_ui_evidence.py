"""v19 state screenshot evidence remains complete and reproducible."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "capture_v19_system_check_states.py"
)


def _load_capture_module():
    spec = importlib.util.spec_from_file_location("capture_v19_states", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("v19 state screenshot validator could not be loaded.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestV19Phase6UiEvidence(unittest.TestCase):
    def test_required_state_screenshots_are_current(self):
        self.assertEqual(_load_capture_module().validate(), [])


if __name__ == "__main__":
    unittest.main()
