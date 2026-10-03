"""Phase 9 tests for logical component availability and core-only startup."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from core.navigation.models import FedoraVariant, NavigationContext, NavigationDecision
from core.navigation.policy import NavigationPolicy
from core.plugins.components import discover_builtin_components, module_source_path
from core.plugins.spec import BUILTIN_PLUGIN_SPECS


ROOT = Path(__file__).parents[1]
SOURCE_ROOT = ROOT / "loofi-fedora-tweaks"


class TestComponentAvailability(unittest.TestCase):
    def test_complete_checkout_exposes_core_and_specialist_components(self):
        self.assertEqual(
            discover_builtin_components(source_root=SOURCE_ROOT),
            frozenset({"core"}),
        )

    def test_one_missing_specialist_module_disables_only_specialist_bundle(self):
        missing = "ui.atlas_dashboard_tab"

        components = discover_builtin_components(
            module_available=lambda module: module != missing
        )

        self.assertEqual(components, frozenset())

    def test_module_paths_are_resolved_without_importing_plugins(self):
        path = module_source_path("ui.atlas_dashboard_tab", source_root=SOURCE_ROOT)

        self.assertEqual(path, SOURCE_ROOT / "ui" / "atlas_dashboard_tab.py")
        self.assertTrue(path.is_file())

    def test_action_center_stays_available_without_specialist_component(self):
        for variant, capabilities in (
            (FedoraVariant.TRADITIONAL, frozenset({"dnf"})),
            (FedoraVariant.ATOMIC, frozenset({"rpm-ostree"})),
        ):
            with self.subTest(variant=variant):
                result = NavigationPolicy.evaluate(
                    "maintenance:action-center",
                    NavigationContext(
                        installed_components=frozenset({"core"}),
                        fedora_variant=variant,
                        capabilities=capabilities,
                    ),
                )
                self.assertEqual(result.decision, NavigationDecision.VISIBLE)




if __name__ == "__main__":
    unittest.main()
