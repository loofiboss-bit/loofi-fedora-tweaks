"""Focused tests for the reproducible v16 Phase 0 inventory."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts.audit_v16_phase0 import (
    BASELINE_TAG,
    build_inventory,
    main,
    render_inventory,
)


class TestV16Phase0Audit(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.inventory = build_inventory()

    def test_release_identity_and_version_are_frozen_at_v15(self):
        release = self.inventory["release_identity"]
        version = self.inventory["versions_and_state_schemas"]["application"]

        self.assertTrue(release["product_matches_baseline"])
        self.assertEqual(release["product_diff"], [])
        self.assertEqual(release["tag_object_type"], "tag")
        self.assertEqual(release["product_tree"], release["baseline_product_tree"])
        self.assertEqual(version["version"], BASELINE_TAG.removeprefix("v"))
        self.assertEqual(version["codename"], "Essentials")
        self.assertEqual(version["version"], version["pyproject_version"])
        self.assertEqual(version["version"], version["rpm_spec_version"])

    def test_navigation_and_lazy_plugin_contract_counts(self):
        navigation = self.inventory["navigation"]

        self.assertEqual(navigation["route_count"], 80)
        self.assertEqual(navigation["alias_key_count"], 438)
        self.assertEqual(len(navigation["alias_keys"]), 438)
        self.assertEqual(len(navigation["destinations"]), 7)
        self.assertEqual(
            [item["id"] for item in navigation["destinations"] if not item["advanced_only"]],
            ["desktop", "home", "network_security", "settings", "software_updates", "system"],
        )
        self.assertEqual(len(navigation["lazy_plugin_specs"]), 28)
        self.assertEqual(navigation["section_metadata_decision"]["classification"], "ADAPT")

    def test_environment_records_os_desktop_qt_and_pyqt_without_probes(self):
        environment = self.inventory["environment"]

        self.assertEqual(
            set(environment["os_release"]),
            {"ID", "PRETTY_NAME", "VARIANT_ID", "VERSION_ID"},
        )
        self.assertEqual(
            set(environment["desktop"]),
            {"current_desktop", "qt_platform", "session_desktop", "session_type"},
        )
        self.assertRegex(environment["qt"]["qt_version"], r"^\d+\.\d+")
        self.assertRegex(environment["qt"]["pyqt_version"], r"^\d+\.\d+")

    def test_action_center_catalog_and_state_schemas_are_frozen(self):
        action_center = self.inventory["action_center"]
        schemas = self.inventory["versions_and_state_schemas"]["action_center"]

        self.assertTrue(action_center["deny_by_default"])
        self.assertEqual(
            [item["id"] for item in action_center["definitions"]],
            ["dnf-clean-all", "fstrim-all", "restart-failed-service"],
        )
        self.assertEqual(schemas["plan_schema_version"], 1)
        self.assertEqual(schemas["run_schema_version"], 1)
        self.assertEqual(schemas["history_schema_version"], 3)
        domain_versions = {
            item["id"]: item["schema_version"]
            for item in self.inventory["versions_and_state_schemas"]["state_domains"]
        }
        self.assertEqual(domain_versions["action_plans"], 1)
        self.assertEqual(domain_versions["action_runs"], 1)
        self.assertEqual(domain_versions["action_history"], 3)

    def test_ui_and_qss_debt_baseline_is_derived(self):
        ui = self.inventory["ui_debt"]
        qss = self.inventory["qss_debt"]

        self.assertEqual(ui["tabs"]["qtabwidget_count"], 16)
        self.assertEqual(ui["tabs"]["qtabwidget_file_count"], 14)
        self.assertEqual(ui["tabs"]["qtabbar_count"], 1)
        self.assertEqual(ui["root_margin_heuristic"]["count"], 65)
        self.assertEqual(ui["inline_styles"]["count"], 30)
        self.assertGreaterEqual(ui["hardcoded_colors"]["count"], 13)
        self.assertGreater(ui["page_title_owners"]["count"], 0)
        self.assertGreater(ui["scroll_owners"]["count"], 0)
        self.assertGreater(ui["full_width_action_heuristic"]["count"], 0)
        self.assertEqual(qss["line_count"], 3358)
        self.assertGreater(qss["broad_selectors"]["count"], 0)

    def test_rendering_and_explicit_output_are_deterministic(self):
        first = render_inventory(build_inventory())
        second = render_inventory(build_inventory())
        self.assertEqual(first, second)
        self.assertEqual(json.loads(first), self.inventory)

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "phase0.json"
            self.assertEqual(main(["--output", str(output)]), 0)
            self.assertEqual(output.read_text(encoding="utf-8"), first)


if __name__ == "__main__":
    unittest.main()
