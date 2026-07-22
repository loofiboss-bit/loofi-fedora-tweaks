"""Phase 9 packaging, dependency, and v14 upgrade compatibility contracts."""

from __future__ import annotations

import json
import tempfile
import tomllib
import unittest
from pathlib import Path

from core.actions.history import ActionHistoryStore
from core.actions.stores import ActionPlanStore, ActionRunStore
from core.navigation.models import NavigationMode
from core.state.doctor import StateDoctor
from core.state.inventory import StateInventory
from core.state.paths import StatePaths
from utils.settings import migrate_settings


ROOT = Path(__file__).parents[1]


class TestPhase9PackageMetadata(unittest.TestCase):
    def test_release_gate_uses_available_local_lint_and_type_tools(self):
        justfile = (ROOT / "Justfile").read_text(encoding="utf-8")

        self.assertIn("[ -x .venv/bin/flake8 ]", justfile)
        self.assertIn("[ -x .venv/bin/mypy ]", justfile)

    def test_base_python_metadata_contains_core_and_secret_store_dependencies(self):
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
            "project"
        ]

        self.assertEqual(project["dependencies"], ["PyQt6>=6.7", "keyring>=25.0"])
        self.assertEqual(
            project["optional-dependencies"]["daemon"], ["dbus-python>=1.3"]
        )
        self.assertNotIn("requests", " ".join(project["dependencies"]))

    def test_rpm_drops_emoji_font_and_preserves_api_daemon_boundaries(self):
        spec = (ROOT / "loofi-fedora-tweaks.spec").read_text(encoding="utf-8")
        api = spec.split("%package api", 1)[1].split("%package daemon", 1)[0]
        daemon = spec.split("%package daemon", 1)[1].split("%prep", 1)[0]

        self.assertNotIn("google-noto-color-emoji-fonts", spec)
        self.assertIn(
            "Requires:       %{name} = %{epoch}:%{version}-%{release}", api
        )
        self.assertIn("Requires:       python3-fastapi", api)
        self.assertIn(
            "Requires:       %{name} = %{epoch}:%{version}-%{release}", daemon
        )
        self.assertIn("Requires:       python3-dbus", daemon)
        self.assertNotIn("%package extras", spec)

    def test_package_descriptions_separate_core_and_specialist_capability(self):
        spec = (ROOT / "loofi-fedora-tweaks.spec").read_text(encoding="utf-8")
        appstream = (ROOT / "loofi-fedora-tweaks.metainfo.xml").read_text(
            encoding="utf-8"
        )

        self.assertIn("Fedora maintenance and desktop control center", spec)
        self.assertIn("Specialist tools", spec)
        self.assertIn(
            "<summary>Fedora maintenance and desktop control center</summary>",
            appstream,
        )
        self.assertIn("Specialist development", appstream)

    def test_rpm_scriptlets_do_not_own_or_migrate_user_state(self):
        spec = (ROOT / "loofi-fedora-tweaks.spec").read_text(encoding="utf-8")
        scriptlets = spec.split("%post api", 1)[1].split("%files", 1)[0]

        for user_state in (
            ".config/loofi-fedora-tweaks",
            ".local/share/loofi-fedora-tweaks",
            "action_center_history.jsonl",
            "action_plans.json",
            "action_runs.jsonl",
        ):
            self.assertNotIn(user_state, scriptlets)


class TestV14UpgradeCompatibility(unittest.TestCase):
    def test_v14_settings_routes_and_action_center_state_are_read_without_mutation(self):
        settings, changed = migrate_settings(
            {
                "experience_level": "intermediate",
                "last_route": "Action Center",
                "favorite_routes": ["Home", "Action Center", "future:route"],
                "state_schema_version": 1,
            }
        )
        self.assertTrue(changed)
        self.assertEqual(settings["navigation_mode"], NavigationMode.ADVANCED.value)
        self.assertEqual(settings["last_route_id"], "maintenance:action-center")
        self.assertEqual(
            settings["favorite_routes"],
            ["atlas_dashboard", "maintenance:action-center", "future:route"],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            paths = StatePaths(
                config=root / "config",
                data=root / "data",
                cache=root / "cache",
                runtime=root / "runtime",
            )
            paths.ensure()
            plan_path = paths.data / "action_plans.json"
            run_path = paths.data / "action_runs.jsonl"
            history_path = paths.data / "action_center_history.jsonl"
            plan_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "plans": [
                            {
                                "plan_id": "v14-plan",
                                "action_id": "dnf-clean-all",
                                "parameters": {},
                                "target": "44",
                                "digest": "fixture",
                                "preview": ["dnf", "clean", "all"],
                                "policy_decision": {
                                    "allowed": True,
                                    "reason_code": "ready",
                                    "explanation": "Ready.",
                                    "facts": {},
                                },
                                "risk_level": "medium",
                                "privileged": True,
                                "confirmation_policy": "explicit-no-rollback",
                                "recovery_guidance": "Review package metadata.",
                                "rollback_supported": False,
                                "state": "ready",
                                "created_at": 1000.0,
                                "expires_at": 2800.0,
                                "state_history": [],
                            }
                        ],
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            run_path.write_text(
                json.dumps(
                    {
                        "action_run_schema_version": 1,
                        "run_id": "v14-run",
                        "plan_id": "v14-plan",
                        "action_id": "dnf-clean-all",
                        "correlation_id": "v14-correlation",
                        "parameters": {},
                        "state": "verifying",
                        "created_at": 1000.0,
                        "updated_at": 1001.0,
                        "started_at": 1000.0,
                        "completed_at": None,
                        "execution_result": {"success": True, "exit_code": 0},
                        "verification_result": None,
                        "recovery_status": "not-required",
                        "state_history": [],
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            history_path.write_text(
                json.dumps(
                    {
                        "action_center_schema_version": 3,
                        "event": "run-awaiting-verification",
                        "run_id": "v14-run",
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            before = {
                path: path.read_bytes()
                for path in (plan_path, run_path, history_path)
            }

            plans = ActionPlanStore(plan_path).list()
            runs = ActionRunStore(run_path).list()
            history = ActionHistoryStore(history_path).recent()
            doctor = StateDoctor(StateInventory(paths)).run()

            self.assertEqual([plan.plan_id for plan in plans], ["v14-plan"])
            self.assertEqual([run.run_id for run in runs], ["v14-run"])
            self.assertEqual(runs[0].state, "verifying")
            self.assertEqual(history[0]["event"], "run-awaiting-verification")
            self.assertNotEqual(doctor["status"], "error")
            self.assertEqual(json.loads(plan_path.read_text(encoding="utf-8"))["schema_version"], 3)
            self.assertEqual(json.loads(run_path.read_text(encoding="utf-8"))["action_run_schema_version"], 3)
            self.assertEqual(history_path.read_bytes(), before[history_path])
            self.assertEqual(plan_path.with_suffix(".json.lkg").read_bytes(), before[plan_path])
            self.assertEqual(run_path.with_suffix(".jsonl.lkg").read_bytes(), before[run_path])


if __name__ == "__main__":
    unittest.main()
