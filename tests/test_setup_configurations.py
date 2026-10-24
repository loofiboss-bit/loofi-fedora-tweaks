"""Portable setup intent and restartable local progress contracts."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.tasks.setup_configurations import (
    SetupApplication,
    SetupDocument,
    SetupLibrary,
    SetupProgressStore,
    available_flatpak_targets,
    compare_setup,
    parse_setup,
    serialize_setup,
)
from core.tasks.tweak_profiles import TweakProfile
from core.tasks.tweaks import TWEAKS, TweakState
from core.state.inventory import StateInventory, StatePaths
from services.software.installed_applications import InstalledApplication, InstalledInventory
from core.tasks import setup_configurations as setup_config_module


def document() -> SetupDocument:
    return SetupDocument("Work", (
        SetupApplication("fedora", "firefox", "firefox", name="Firefox"),
        SetupApplication("flatpak", "org.gimp.GIMP", "app/org.gimp.GIMP/x86_64/stable", "user", name="GIMP"),
    ), TweakProfile("Comfort", "kde", (("kde-single-click", "false"),)))


class SetupConfigurationTests(unittest.TestCase):
    def test_local_library_and_progress_are_registered_in_private_backup_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inventory = StateInventory(StatePaths(root / "config", root / "data", root / "cache", root / "run"))

            library = inventory.get("setup_library")
            progress = inventory.get("setup_runs")

        self.assertEqual(library.schema_id, "loofi.setup-library")
        self.assertEqual(progress.schema_id, "loofi.setup-runs")
        self.assertEqual(library.sensitivity, "private")
        self.assertEqual(progress.sensitivity, "private")
        self.assertEqual(library.category, "data")
        self.assertEqual(progress.category, "data")

    def test_round_trip_preserves_scoped_application_intent_and_embedded_profile(self) -> None:
        actual = parse_setup(serialize_setup(document()))

        self.assertEqual(actual, document())
        self.assertEqual(actual.applications[1].installation, "user")
        self.assertEqual(actual.profile.settings, (("kde-single-click", "false"),))

    def test_rejects_unknown_schema_commands_urls_paths_and_duplicate_json_keys(self) -> None:
        payload = document().to_dict()
        payload["schema"] = "loofi.setup/v2"
        with self.assertRaisesRegex(ValueError, "Unsupported setup"):
            parse_setup(json.dumps(payload).encode())

        payload = document().to_dict()
        payload["applications"][1]["source_hint"] = "https://example.test/repo"
        with self.assertRaisesRegex(ValueError, "source hints"):
            parse_setup(json.dumps(payload).encode())

        payload = document().to_dict()
        payload["applications"][0]["command"] = ["dnf", "install"]
        with self.assertRaises(ValueError):
            parse_setup(json.dumps(payload).encode())
        with self.assertRaisesRegex(ValueError, "duplicate JSON"):
            parse_setup(b'{"schema":"loofi.setup/v1","name":"a","name":"b","applications":[],"profile":{}}')

    def test_compare_distinguishes_exact_installation_and_unknown_source(self) -> None:
        expected = document()
        rpm = InstalledApplication("Firefox", "firefox", "fedora", "system", "firefox")
        elsewhere = InstalledApplication("GIMP", "org.gimp.GIMP", "flatpak", "system", "app/org.gimp.GIMP/x86_64/stable")
        tweak = next(item for item in TWEAKS if item.id == "kde-single-click")
        states = (TweakState(tweak, "ready", "true", tweak.choices),)

        result = compare_setup(expected, expected.digest, InstalledInventory((rpm, elsewhere)), states)

        self.assertEqual([entry.status for entry in result.entries], ["present", "other_installation", "differs"])
        self.assertGreater(result.sampled_at, 0)
        unavailable = compare_setup(expected, expected.digest, InstalledInventory(unknown_sources=frozenset({"fedora"})), states)
        self.assertEqual(unavailable.entries[0].status, "unavailable")

    def test_named_flatpak_target_requires_local_confirmation_and_keeps_scope_identity(self) -> None:
        app = SetupApplication("flatpak", "org.gimp.GIMP", "app/org.gimp.GIMP/x86_64/stable", "archive")
        expected = SetupDocument("Work", (app,), TweakProfile("Work", "kde", ()))
        installed = InstalledApplication("GIMP", app.app_id, "flatpak", "work", app.ref)

        needs_target = compare_setup(expected, expected.digest, InstalledInventory((installed,)), ())
        confirmed = compare_setup(expected, expected.digest, InstalledInventory((installed,)), (),
                                  target_installations={app.identity: "work"})
        invalid_target = compare_setup(expected, expected.digest, InstalledInventory((installed,)), (),
                                       target_installations={app.identity: "../work"})

        self.assertEqual(needs_target.entries[0].status, "needs_target")
        self.assertEqual(confirmed.entries[0].status, "present")
        self.assertEqual(invalid_target.entries[0].status, "needs_target")

    def test_named_flatpak_target_does_not_collapse_an_explicit_user_installation(self) -> None:
        ref = "app/org.gimp.GIMP/x86_64/stable"

        choices = available_flatpak_targets(ref, ("user", "system", "work"), {(ref, "user")})

        self.assertEqual(choices, ("system", "work"))

    def test_explicit_host_desktop_and_skipped_progress_are_not_success(self) -> None:
        expected = document()
        states = ()
        result = compare_setup(expected, expected.digest, InstalledInventory(), states, current_desktop="gnome")
        self.assertEqual(result.entries[-1].status, "wrong_desktop")
        with tempfile.TemporaryDirectory() as directory:
            store = SetupProgressStore(Path(directory) / "runs.json")
            app_step = f"app:{expected.applications[0].identity}"
            setting_step = "setting:kde-single-click"
            run_id = store.start(expected.digest, expected.digest, (app_step, setting_step))
            store.update(run_id, app_step, "skipped")
            self.assertEqual(store.list()[0]["status"], "partial")

    def test_future_library_schema_is_preserved_when_add_is_attempted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "setups.json"
            original = b'{"schema_id":"loofi.setup-library","schema_version":2,"setups":[]}'
            path.write_bytes(original)
            with self.assertRaisesRegex(ValueError, "unsupported"):
                SetupLibrary(path).add(document())
            self.assertEqual(path.read_bytes(), original)

    def test_library_is_content_addressed_bounded_and_keeps_invalid_existing_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            library = SetupLibrary(Path(directory) / "setups.json")
            identifier = library.add(document())
            self.assertEqual(library.add(document()), identifier)
            self.assertEqual(library.get(identifier), document())
            self.assertEqual(library.list("firefox")[0][0], identifier)
            library.remove(identifier)
            self.assertEqual(library.list(), ())

    def test_library_checks_the_exact_pretty_json_size_before_replacing_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            library = SetupLibrary(Path(directory) / "setups.json")
            first_id = library.add(document())
            second = SetupDocument("Creative", document().applications, document().profile)
            records = library._read() + [{"id": second.digest, "document": second.to_dict()}]
            payload = {"schema_id": "loofi.setup-library", "schema_version": 1, "setups": records}
            compact_size = len(json.dumps(payload, ensure_ascii=False).encode())
            stored_size = len(json.dumps(payload, indent=2, sort_keys=True, default=str).encode())
            self.assertLess(compact_size, stored_size)

            with patch.object(setup_config_module, "MAX_LIBRARY_BYTES", stored_size - 1):
                with self.assertRaisesRegex(ValueError, "size limit"):
                    library.add(second)

            self.assertEqual([identifier for identifier, _doc in library.list()], [first_id])

    def test_progress_prunes_old_completed_runs_before_exceeding_read_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runs.json"
            store = SetupProgressStore(path)
            setup_id = document().digest
            step = f"app:{document().applications[0].identity}"
            latest_id = ""

            with patch.object(setup_config_module, "MAX_PROGRESS_BYTES", 1_500):
                for _index in range(12):
                    latest_id = store.start(setup_id, setup_id, (step,))
                    store.update(latest_id, step, "succeeded", plan_id="review-plan", action_run_id="verified-run")
                    self.assertLessEqual(path.stat().st_size, 1_500)
                    self.assertTrue(store.list())

                records = store.list()

        self.assertLess(len(records), 12)
        self.assertEqual(records[-1]["id"], latest_id)

    def test_reconcile_does_not_apply_an_observation_from_a_different_flatpak_target(self) -> None:
        app = SetupApplication("flatpak", "org.gimp.GIMP", "app/org.gimp.GIMP/x86_64/stable", "office")
        expected = SetupDocument("Work", (app,), TweakProfile("Work", "kde", ()))
        step = f"app:{app.identity}"
        with tempfile.TemporaryDirectory() as directory:
            store = SetupProgressStore(Path(directory) / "runs.json")
            run_id = store.start(expected.digest, expected.digest, (step,),
                                 target_installations={app.identity: "work"})
            store.update(run_id, step, "running", plan_id="office-plan", action_run_id="office-run")
            comparison = compare_setup(
                expected, expected.digest,
                InstalledInventory((InstalledApplication("GIMP", app.app_id, "flatpak", "user", app.ref),)), (),
                target_installations={app.identity: "user"},
            )
            store.reconcile(expected.digest, expected.digest, comparison,
                            target_installations={app.identity: "user"})

            resumed = store.list()[0]

        self.assertEqual(resumed["steps"][step]["status"], "unavailable")
        self.assertEqual(resumed["steps"][step]["run_id"], "office-run")

    def test_progress_survives_reopen_and_binds_real_action_references(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runs.json"
            store = SetupProgressStore(path)
            setup_id = document().digest
            app_step = f"app:{document().applications[0].identity}"
            setting_step = "setting:kde-single-click"
            run_id = store.start(setup_id, setup_id, (app_step, setting_step))
            store.update(run_id, app_step, "succeeded", plan_id="plan-1", action_run_id="run-1")

            resumed = SetupProgressStore(path).list()[0]
            self.assertEqual(resumed["steps"][app_step]["plan_id"], "plan-1")
            self.assertEqual(resumed["steps"][app_step]["run_id"], "run-1")
            self.assertEqual(resumed["steps"][setting_step]["status"], "not_started")

    def test_reconcile_after_interruption_uses_fresh_state_without_claiming_a_new_action(self) -> None:
        expected = document()
        app = expected.applications[0]
        with tempfile.TemporaryDirectory() as directory:
            store = SetupProgressStore(Path(directory) / "runs.json")
            app_step = f"app:{app.identity}"
            setting_step = "setting:kde-single-click"
            run_id = store.start(expected.digest, expected.digest, (app_step, setting_step))
            store.update(run_id, app_step, "running", plan_id="plan-running", action_run_id="run-running")
            store.update(run_id, setting_step, "running")

            current = compare_setup(
                expected, expected.digest,
                InstalledInventory((InstalledApplication("Firefox", "firefox", "fedora", "system", "firefox"),)),
                (TweakState(next(item for item in TWEAKS if item.id == "kde-single-click"), "ready", "false", ()),),
            )
            store.reconcile(expected.digest, expected.digest, current)

            resumed = SetupProgressStore(Path(directory) / "runs.json").list()[0]

        self.assertEqual(resumed["status"], "completed")
        self.assertEqual(resumed["steps"][app_step]["status"], "satisfied")
        self.assertEqual(resumed["steps"][app_step]["plan_id"], "plan-running")
        self.assertEqual(resumed["steps"][app_step]["run_id"], "run-running")
        self.assertEqual(resumed["steps"][setting_step]["status"], "satisfied")

    def test_hard_process_exit_reopens_and_reconciles_before_a_new_review(self) -> None:
        expected = document()
        present, missing = expected.applications
        states = (TweakState(next(item for item in TWEAKS if item.id == "kde-single-click"),
                             "ready", "false", ()),)
        comparison = compare_setup(
            expected, expected.digest,
            InstalledInventory((InstalledApplication("Firefox", "firefox", "fedora", "system", "firefox"),)),
            states, current_desktop="kde", sampled_at=1_800_000_000.0,
        )
        present_step = f"app:{present.identity}"
        missing_step = f"app:{missing.identity}"
        setting_step = "setting:kde-single-click"

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            library = SetupLibrary(root / "setups.json")
            setup_id = library.add(parse_setup(serialize_setup(expected)))
            progress_path = root / "runs.json"
            crash_writer = r"""
import os
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from core.tasks.setup_configurations import SetupProgressStore

repository, path, setup_id, digest, present_step, missing_step, setting_step = sys.argv[1:]
store = SetupProgressStore(Path(path))
run_id = store.start(setup_id, digest, (present_step, missing_step, setting_step))
for step, plan_id, action_run_id in (
    (present_step, "plan-present", "run-present"),
    (missing_step, "plan-missing", "run-missing"),
    (setting_step, "plan-setting", "run-setting"),
):
    store.update(run_id, step, "running", plan_id=plan_id, action_run_id=action_run_id)
os._exit(86)
"""
            crashed = subprocess.run(
                [sys.executable, "-c", crash_writer, str(Path(__file__).parents[1] / "loofi-fedora-tweaks"),
                 str(progress_path), setup_id, expected.digest, present_step, missing_step, setting_step],
                check=False, timeout=30, capture_output=True, text=True, env={**os.environ},
            )
            self.assertEqual(crashed.returncode, 86, crashed.stderr)

            reopened = SetupProgressStore(progress_path)
            reopened.reconcile(setup_id, expected.digest, comparison)
            interrupted = reopened.list()[0]
            next_review = reopened.start(setup_id, expected.digest, (missing_step,))
            next_attempt = next(item for item in reopened.list() if item["id"] == next_review)

        self.assertEqual(interrupted["status"], "partial")
        self.assertEqual(interrupted["steps"][present_step]["status"], "satisfied")
        self.assertEqual(interrupted["steps"][present_step]["plan_id"], "plan-present")
        self.assertEqual(interrupted["steps"][present_step]["run_id"], "run-present")
        self.assertEqual(interrupted["steps"][missing_step]["status"], "interrupted")
        self.assertEqual(interrupted["steps"][setting_step]["status"], "satisfied")
        self.assertEqual(next_attempt["steps"][missing_step], {"status": "not_started"})


if __name__ == "__main__":
    unittest.main()
