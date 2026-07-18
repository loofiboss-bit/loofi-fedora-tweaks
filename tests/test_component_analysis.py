"""Tests for deterministic Phase 9 component-boundary evidence."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "analyze_component_boundaries.py"
SPEC = importlib.util.spec_from_file_location("analyze_component_boundaries", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)


class TestComponentGraph(unittest.TestCase):
    def test_graph_resolves_absolute_and_relative_internal_imports(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "pkg").mkdir()
            (root / "pkg" / "__init__.py").write_text(
                "from . import helper\n", encoding="utf-8"
            )
            (root / "pkg" / "helper.py").write_text(
                "from shared import value\n", encoding="utf-8"
            )
            (root / "shared.py").write_text("value = 1\n", encoding="utf-8")

            modules = analysis.discover_modules(root)
            graph = analysis.build_import_graph(modules)

        self.assertEqual(graph["pkg"], {"pkg.helper"})
        self.assertEqual(graph["pkg.helper"], {"shared"})
        self.assertEqual(
            analysis.reachable_modules(graph, {"pkg"}),
            {"pkg", "pkg.helper", "shared"},
        )

    def test_live_report_captures_logical_components_and_rpm_constraints(self):
        report = analysis.analyze()

        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["components"]["core"]["entry_module_count"], 17)
        self.assertEqual(
            report["components"]["specialist"]["entry_module_count"], 11
        )
        self.assertEqual(report["graph"]["missing_entry_modules"], [])
        self.assertGreater(report["graph"]["project_module_count"], 100)
        self.assertGreater(
            report["surface_reachability"]["cli"]["reachable_count"], 0
        )
        self.assertGreater(
            report["surface_reachability"]["api"]["specialist_exclusive_count"],
            0,
        )
        self.assertTrue(report["rpm"]["base_owns_complete_application_tree"])
        self.assertFalse(report["rpm"]["extras_subpackage_defined"])
        self.assertTrue(report["rpm"]["api_requires_exact_base"])
        self.assertTrue(report["rpm"]["daemon_requires_exact_base"])


if __name__ == "__main__":
    unittest.main()
