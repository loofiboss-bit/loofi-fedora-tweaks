"""Phase 6 contracts for Advanced adoption and legacy UI cleanup."""

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

from core.navigation import placement_for_route, sections_for_destination


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "validate_v16_phase6_ui.py"


def _load_validator():
    spec = importlib.util.spec_from_file_location("v16_phase6_validator", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TestV16Phase6Validator(unittest.TestCase):
    def test_static_contract_validation_passes_without_host_probe(self):
        self.assertEqual(_load_validator().validate(), [])

    def test_json_cli_reports_advanced_cleanup_without_mutations(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--json"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )

        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(payload["advanced_pages"], 12)
        self.assertEqual(payload["advanced_routes"], 33)
        self.assertEqual(payload["advanced_sections"], 26)
        self.assertEqual(payload["application_navigation_qtabwidgets"], 0)
        self.assertEqual(payload["local_tab_views"], 3)
        self.assertEqual(payload["host_probes"], 0)
        self.assertEqual(payload["mutations"], 0)
        self.assertEqual(payload["status"], "passed")


class TestAdvancedSectionPlacement(unittest.TestCase):
    def test_shell_exposes_every_advanced_route_page(self):
        sections = sections_for_destination("advanced")
        defaults = {section.default_route_id for section in sections}
        self.assertEqual(len(sections), 26)
        for route_id in (
            "development:developer",
            "community:marketplace",
            "community:plugins",
            "community:featured",
            "loofi-link:clipboard",
            "loofi-link:file-drop",
            "ai-lab:voice",
            "ai-lab:knowledge",
            "agents:my-agents",
            "agents:create",
            "agents:activity",
            "automation:replicator",
            "virtualization:gpu-passthrough",
            "virtualization:disposable",
        ):
            with self.subTest(route_id=route_id):
                placement = placement_for_route(route_id)
                self.assertIsNotNone(placement)
                self.assertEqual(placement.destination_id, "advanced")
                self.assertIn(route_id, defaults)


if __name__ == "__main__":
    unittest.main()
