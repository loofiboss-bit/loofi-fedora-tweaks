"""Regressions for review controls on small work areas and enlarged text."""

import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import json
import subprocess
import tempfile


class TestReviewAccessibilityMatrix(unittest.TestCase):
    @patch("sys.argv", new_callable=list)
    @patch("builtins.print")
    @patch("subprocess.run")
    def test_matrix_children_isolate_all_xdg_storage(self, mock_run, _print, arguments):
        path = Path(__file__).resolve().parents[1] / "scripts" / "check_gui_accessibility.py"
        spec = importlib.util.spec_from_file_location("gui_accessibility_matrix_isolation", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        environments = []

        def run(command, **kwargs):
            environments.append(kwargs["env"])
            return subprocess.CompletedProcess(command, 0, json.dumps({"checks": []}), "")

        with tempfile.TemporaryDirectory() as output:
            mock_run.side_effect = run
            arguments.extend([str(path), "--output-dir", output])
            self.assertEqual(module.main(), 0)
        self.assertEqual(len(environments), 24)
        for env in environments:
            for kind in ("CONFIG", "DATA", "CACHE", "STATE"):
                self.assertIn("loofi-accessibility-", env[f"XDG_{kind}_HOME"])

    def test_three_themes_and_enlarged_text_keep_primary_controls_reachable(self):
        path = Path(__file__).resolve().parents[1] / "scripts" / "check_gui_accessibility.py"
        spec = importlib.util.spec_from_file_location("gui_accessibility_matrix", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for theme in ("light", "dark", "highcontrast"):
            for points in (12, 18):
                with self.subTest(theme=theme, points=points):
                    report = module.check_case(theme, points)
                    self.assertIn("space_accepts_explicitly", report["checks"])
                    self.assertLessEqual(report["dialog_size"][0], report["logical_test_area"][0])
