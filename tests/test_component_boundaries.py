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
            frozenset({"core", "specialist"}),
        )

    def test_one_missing_specialist_module_disables_only_specialist_bundle(self):
        missing = "ui.ai_enhanced_tab"

        components = discover_builtin_components(
            module_available=lambda module: module != missing
        )

        self.assertEqual(components, frozenset({"core"}))

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


class TestCoreOnlyStartup(unittest.TestCase):
    def test_home_renders_when_specialist_plugin_files_are_absent(self):
        specialist_files = {
            Path(*spec.module.split(".")).with_suffix(".py")
            for spec in BUILTIN_PLUGIN_SPECS
            if spec.component == "specialist"
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            copied_source = Path(tmpdir) / "loofi-fedora-tweaks"

            def ignore(directory: str, names: list[str]) -> set[str]:
                relative = Path(directory).relative_to(SOURCE_ROOT)
                ignored = {"__pycache__"} if "__pycache__" in names else set()
                for name in names:
                    if relative / name in specialist_files:
                        ignored.add(name)
                return ignored

            shutil.copytree(SOURCE_ROOT, copied_source, ignore=ignore)
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(copied_source)
            environment["LOOFI_SOURCE_ROOT"] = str(copied_source)
            contract = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "verify_core_component.py"),
                    "--json",
                ],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
                timeout=30,
            )
            self.assertEqual(contract.returncode, 0, contract.stderr)
            core_contract = json.loads(contract.stdout)

            output = Path(tmpdir) / "core-only-startup.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "benchmark_startup.py"),
                    "--warmups",
                    "0",
                    "--runs",
                    "1",
                    "--output",
                    str(output),
                ],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
                timeout=30,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            run = json.loads(output.read_text(encoding="utf-8"))["runs"][0]

        self.assertEqual(core_contract["status"], "passed")
        self.assertEqual(len(core_contract["standard_destinations"]), 6)
        self.assertEqual(len(core_contract["core_workflows"]), 5)
        self.assertEqual(
            core_contract["action_center_variants"],
            {"atomic": "visible", "traditional": "visible"},
        )
        self.assertEqual(core_contract["imported_specialist_modules"], [])
        self.assertEqual(core_contract["host_probes"], 0)
        self.assertEqual(core_contract["mutations"], 0)
        self.assertEqual(run["installed_components"], ["core"])
        self.assertEqual(run["runtime_plugin_ids"], ["atlas_dashboard"])
        self.assertEqual(run["plugin_spec_count"], len(BUILTIN_PLUGIN_SPECS))
        self.assertEqual(run["subprocess_probes"], [])
        self.assertEqual(run["running_qthreads"], 0)
        specialist_modules = {spec.module for spec in BUILTIN_PLUGIN_SPECS if spec.component == "specialist"}
        self.assertTrue(specialist_modules.isdisjoint(run["imports"]["ui_modules"]))


if __name__ == "__main__":
    unittest.main()
