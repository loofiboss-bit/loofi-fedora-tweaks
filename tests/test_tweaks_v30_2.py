"""Comfort settings and durable one-step restoration regression coverage."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

from core.actions.catalog import ActionCatalog
from core.actions.contracts import ActionRun
from core.actions.operation_controller import OperationController
from core.actions.orchestrator import ActionCenterOrchestrator
from core.actions.stores import ActionPlanStore, ActionRunStore
from core.executor.action_result import ActionResult
from core.executor.command_policy import CommandValidationError, validate_command_vector
from core.tasks.tweak_history import read_tweak_runs, restoration_for
from core.tasks.tweaks import BY_ID, TWEAKS, command_for, read_tweak, snapshot
from core.tweak_commands import valid_value, values_equal
from test_tweaks_v30_1 import FakeRuntime, profile


def change(tweak_id="gnome-battery", before="false", after="true", *, created=1.0):
    return ActionRun(
        run_id="source-run", plan_id="source-plan", action_id=BY_ID[tweak_id].action_id,
        correlation_id="source-correlation", parameters={"value": after},
        affected_resources=(f"tweak:{tweak_id}",), state="succeeded", created_at=created,
        execution_result={"success": True},
        verification_result={"success": True, "data": {"tweak_change": {
            "version": 1, "kind": "change", "tweak_id": tweak_id, "before": before, "after": after,
        }}},
    )


class HistoryRuntime(FakeRuntime):
    def __init__(self, desktop="gnome", store=None):
        super().__init__(desktop)
        self.store = store
        self.runs = []

    def tweak_runs(self):
        return self.store.list_read_only(strict=True) if self.store else tuple(self.runs)

    def is_atomic(self):
        return self._profile.deployment_backend.value == "rpm_ostree"

    def fedora_version(self):
        return "44"

    def boot_id(self):
        return "test-boot"

    def package_manager(self):
        return "rpm-ostree" if self.is_atomic() else "dnf5"


@patch("core.tasks.tweaks.kde_capability_error", return_value="")
class TestComfortValues(unittest.TestCase):
    @patch("core.tasks.tweaks.shutil.which", return_value="/usr/bin/dolphin")
    def test_all_controls_read_on_both_fedora_deployments(self, _which, _capability):
        for backend in ("dnf5", "rpm_ostree"):
            for desktop in ("gnome", "kde"):
                runtime = FakeRuntime(desktop, backend)
                for tweak in TWEAKS:
                    state = read_tweak(tweak, runtime.platform_profile(), runtime.execute_read_only)
                    with self.subTest(backend=backend, desktop=desktop, tweak=tweak.id):
                        self.assertEqual(state.status, "ready" if tweak.desktop in {desktop, "all"} else "unavailable")
                        for value, _label in state.choices:
                            validate_command_vector(command_for(tweak, value))

    def test_malformed_and_missing_reads_never_enable_changes(self, _capability):
        for tweak in TWEAKS:
            runtime = FakeRuntime("kde" if tweak.desktop == "kde" else "gnome")
            runtime.output[tweak.id] = "not-a-setting\n"
            if tweak.id == "kde-color":
                runtime.kde_color_current = ""
            with self.subTest(tweak=tweak.id):
                self.assertNotEqual(read_tweak(tweak, runtime.platform_profile(), runtime.execute_read_only).status, "ready")
                runtime.fail = True
                self.assertEqual(read_tweak(tweak, runtime.platform_profile(), runtime.execute_read_only).status, "unavailable")

    def test_unsupported_profiles_never_probe_host(self, _capability):
        reader = Mock()
        for desktop, backend in (("unknown", "dnf5"), ("kde", "bootc")):
            for tweak in TWEAKS:
                self.assertEqual(read_tweak(tweak, profile(desktop, backend), reader).status, "unavailable")
        reader.assert_not_called()

    def test_custom_numeric_values_are_precise_but_not_normal_choices(self, _capability):
        for tweak_id, value in (("kde-animation", "0.70710678"), ("gnome-text-scale", "1.234567890123456789"), ("kde-double-click-interval", "537")):
            self.assertTrue(valid_value(tweak_id, value))
            self.assertTrue(values_equal(tweak_id, value, value))
            with self.assertRaises(ValueError):
                command_for(BY_ID[tweak_id], value)
            validate_command_vector(command_for(BY_ID[tweak_id], value, restoring=True))
        self.assertFalse(values_equal("kde-animation", "0.70710678", "0.707107"))

    def test_numeric_boundaries_and_nonfinite_literals_fail_closed(self, _capability):
        invalid = {
            "gnome-text-scale": ("0.49", "3.01", "NaN", "inf", "-1"),
            "kde-animation": ("-0.1", "NaN", "inf", "1e999", "1;echo bad"),
            "kde-double-click-interval": ("99", "2001", "400.0", "4e2", "４００"),
        }
        for tweak_id, values in invalid.items():
            for value in values:
                with self.subTest(tweak=tweak_id, value=value):
                    self.assertFalse(valid_value(tweak_id, value))
                    with self.assertRaises(ValueError):
                        command_for(BY_ID[tweak_id], value, restoring=True)

    def test_custom_numeric_execution_requires_matching_restore_authority(self, _capability):
        from core.execution_policy import execution_allowed
        for tweak_id, value in (("kde-animation", "0.70710678"), ("gnome-text-scale", "1.23456789"), ("kde-double-click-interval", "537")):
            canonical = command_for(BY_ID[tweak_id], value, restoring=True)
            for vector in (canonical, ["flatpak-spawn", "--host", *canonical]):
                with self.subTest(tweak=tweak_id, binary=vector[0]):
                    self.assertFalse(execution_allowed(vector[0], vector[1:]))
                    self.assertFalse(execution_allowed(vector[0], vector[1:], action_id=f"restore-{tweak_id}"))
                    self.assertFalse(execution_allowed(vector[0], vector[1:], authority="action_center"))
                    self.assertFalse(execution_allowed(vector[0], vector[1:], authority="action_center", action_id=f"set-{tweak_id}"))
                    self.assertFalse(execution_allowed(vector[0], vector[1:], authority="action_center", action_id="restore-gnome-battery"))
                    self.assertTrue(execution_allowed(vector[0], vector[1:], authority="action_center", action_id=f"restore-{tweak_id}"))
            for privileged in (["pkexec", *canonical], ["flatpak-spawn", "--host", "pkexec", *canonical], ["pkexec", "flatpak-spawn", "--host", *canonical]):
                with self.subTest(tweak=tweak_id, privileged=privileged):
                    self.assertFalse(execution_allowed(privileged[0], privileged[1:], authority="action_center", action_id=f"restore-{tweak_id}"))

    @patch("core.tasks.tweaks.shutil.which", return_value="/usr/bin/dolphin")
    def test_each_action_requires_successful_target_readback(self, _which, _capability):
        from types import SimpleNamespace
        catalog = ActionCatalog()
        for tweak in TWEAKS:
            runtime = FakeRuntime("kde" if tweak.desktop == "kde" else "gnome")
            state = read_tweak(tweak, runtime.platform_profile(), runtime.execute_read_only)
            target = state.choices[0][0]
            definition = catalog.get(tweak.action_id)
            plan = SimpleNamespace(parameters={"value": target}, policy_decision=SimpleNamespace(facts={"current": state.value}))
            run = SimpleNamespace(action_id=tweak.action_id)
            runtime.output[tweak.id] = target + "\n"
            if tweak.id == "kde-color":
                runtime.output[tweak.id] = " * BreezeDark\n * CustomTheme\n"
                runtime.kde_color_current = target + "\n"
            with self.subTest(tweak=tweak.id):
                self.assertEqual(definition.verifier(run, plan, runtime).state, "succeeded")
                runtime.fail = True
                self.assertEqual(definition.verifier(run, plan, runtime).state, "failed")

    def test_exact_kde_keys_cannot_be_repurposed(self, _capability):
        for tweak_id in ("kde-single-click", "kde-double-click-interval", "kde-smooth-scroll", "kde-scrollbar-click"):
            vector = command_for(BY_ID[tweak_id], BY_ID[tweak_id].choices[0][0])
            for index, replacement in ((1, "--delete"), (3, "kscreenlockerrc"), (5, "Daemon"), (7, "Autolock")):
                invalid = list(vector)
                invalid[index] = replacement
                with self.subTest(tweak=tweak_id, index=index), self.assertRaises(CommandValidationError):
                    validate_command_vector(invalid)
            with self.assertRaises(CommandValidationError):
                validate_command_vector(vector + ["--delete"])


@patch("core.tasks.tweaks.kde_capability_error", return_value="")
class TestRestoreHistory(unittest.TestCase):
    def setUp(self):
        self.runtime = HistoryRuntime()
        self.runtime.output["gnome-battery"] = "true\n"
        self.tweak = BY_ID["gnome-battery"]
        self.run = change()

    def offer(self, runs=None):
        state = read_tweak(self.tweak, self.runtime.platform_profile(), self.runtime.execute_read_only)
        return restoration_for(self.tweak, state, [self.run] if runs is None else runs)

    def test_latest_verified_change_survives_store_restart(self, _capability):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runs.jsonl"
            ActionRunStore(path).save(self.run)
            self.runtime.store = ActionRunStore(path)
            state = next(item for item in snapshot(self.runtime.platform_profile(), self.runtime) if item.tweak.id == self.tweak.id)
            self.assertEqual(state.restore_run_id, self.run.run_id)
            self.assertEqual(state.restore_value, "false")
            self.assertEqual(json.loads(path.read_text().splitlines()[0])["action_run_schema_version"], 4)

    def test_later_unsuccessful_or_pending_attempt_blocks_older_success(self, _capability):
        for action_id in (self.tweak.action_id, "restore-gnome-battery"):
            for state in ("failed", "verification_failed", "interrupted", "cancelled", "running", "verifying"):
                later = replace(self.run, run_id="later", action_id=action_id, state=state, created_at=2)
                with self.subTest(action=action_id, state=state):
                    self.assertFalse(self.offer([self.run, later]).source_run_id)

    def test_restore_success_consumes_offer_and_new_change_replaces_it(self, _capability):
        restored = replace(self.run, run_id="restored", action_id="restore-gnome-battery", created_at=2)
        self.assertFalse(self.offer([self.run, restored]).source_run_id)
        newer = replace(self.run, run_id="newer", created_at=3)
        self.assertEqual(self.offer([self.run, restored, newer]).source_run_id, "newer")

    def test_external_drift_legacy_or_unverified_metadata_blocks_restore(self, _capability):
        self.runtime.output["gnome-battery"] = "false\n"
        self.assertIn("outside Loofi", self.offer().message)
        self.runtime.output["gnome-battery"] = "true\n"
        for verification in ({"success": True}, {"success": False, "data": self.run.verification_result["data"]}):
            self.assertFalse(self.offer([replace(self.run, verification_result=verification)]).source_run_id)
        self.assertFalse(self.offer([replace(self.run, execution_result={"success": False})]).source_run_id)
        self.assertFalse(self.offer([replace(self.run, parameters={"value": "false"})]).source_run_id)

    def test_malformed_metadata_is_never_restorable(self, _capability):
        original = self.run.verification_result["data"]["tweak_change"]
        for field, value in (("version", True), ("version", 2), ("kind", "restore"), ("tweak_id", "kde-animation"), ("before", "unsafe"), ("after", "false"), ("before", False)):
            record = {**original, field: value}
            run = replace(self.run, verification_result={"success": True, "data": {"tweak_change": record}})
            with self.subTest(field=field, value=value):
                self.assertFalse(self.offer([run]).source_run_id)

    def test_removed_scheme_or_power_profile_is_blocked(self, _capability):
        for tweak_id, before, after in (("kde-color", "RemovedTheme", "CustomTheme"), ("power-profile", "performance", "balanced")):
            runtime = HistoryRuntime("kde")
            if tweak_id == "power-profile":
                original = runtime.execute_read_only
                runtime.execute_read_only = lambda vector, **kwargs: ActionResult.ok("list", stdout="* balanced:\n  power-saver:\n") if tuple(vector) == ("powerprofilesctl", "list") else original(vector, **kwargs)
            tweak = BY_ID[tweak_id]
            state = read_tweak(tweak, runtime.platform_profile(), runtime.execute_read_only)
            self.assertIn("no longer available", restoration_for(tweak, state, [change(tweak_id, before, after)]).message)

    def test_corrupt_record_invalidates_history_without_rewriting_it(self, _capability):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runs.jsonl"
            store = ActionRunStore(path)
            store.save(self.run)
            path.write_text(path.read_text() + "{invalid record\n")
            before = path.read_bytes()
            self.runtime.store = store
            runs, error = read_tweak_runs(self.runtime)
            self.assertEqual(runs, ())
            self.assertTrue(error)
            self.assertEqual(path.read_bytes(), before)
            state = next(item for item in snapshot(self.runtime.platform_profile(), self.runtime) if item.tweak.id == "gnome-battery")
            self.assertFalse(state.restore_run_id)
            self.assertTrue(state.restore_message)

    def test_restore_parameters_cannot_override_saved_value(self, _capability):
        self.runtime.runs = [self.run]
        definition = ActionCatalog().get("restore-gnome-battery")
        self.assertEqual(set(definition.parameter_schema), {"source_run_id"})
        self.assertTrue(definition.preflight_checker({"source_run_id": self.run.run_id}, self.runtime).allowed)
        for parameters in ({"source_run_id": self.run.run_id, "value": "false"}, {"source_run_id": "missing"}, {"source_run_id": "../secret"}):
            self.assertFalse(definition.preflight_checker(parameters, self.runtime).allowed)
            with self.assertRaises(ValueError):
                definition.command_renderer(parameters, self.runtime)

    @patch.object(HistoryRuntime, "tweak_runs", side_effect=OSError("unreadable"))
    def test_unreadable_history_grants_no_restore_authority(self, _reader, _capability):
        runs, error = read_tweak_runs(self.runtime)
        self.assertEqual(runs, ())
        self.assertTrue(error)


@patch("core.tasks.tweaks.kde_capability_error", return_value="")
class TestComfortOperationIntegration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.store = ActionRunStore(root / "runs.jsonl")
        self.runtime = HistoryRuntime(store=self.store)
        self.facade = Mock()
        ids = iter(f"comfort-{index}" for index in range(1000))
        self.orchestrator = ActionCenterOrchestrator(
            facade=self.facade, runtime=self.runtime, plan_store=ActionPlanStore(root / "plans.json"),
            run_store=self.store, lease_path=root / "lease", id_factory=lambda: next(ids),
        )
        self.controller = OperationController(orchestrator=self.orchestrator, facade=self.facade)

    def tearDown(self):
        self.temp.cleanup()

    def execute_setting(self, vector, **kwargs):
        self.assertEqual(kwargs["authority"], "action_center")
        action_id = kwargs["action_id"]
        tweak_id = action_id.removeprefix("set-").removeprefix("restore-")
        self.runtime.output[tweak_id] = vector[-1] + "\n"
        return ActionResult.ok("executed", exit_code=0, action_id=action_id)

    def changed(self):
        outcome = self.controller.execute("set-gnome-battery", {"value": "true"}, confirmed=True, executor=self.execute_setting)
        self.assertTrue(outcome.success, outcome.message)
        return outcome

    def test_real_controller_persists_metadata_then_executes_distinct_restore(self, _capability):
        original = self.changed()
        saved = ActionRunStore(self.store.path).get(original.run_id)
        record = saved.verification_result["data"]["tweak_change"]
        self.assertEqual(record, {"version": 1, "kind": "change", "tweak_id": "gnome-battery", "before": "false", "after": "true"})
        restored = self.controller.execute("restore-gnome-battery", {"source_run_id": saved.run_id}, confirmed=True, executor=self.execute_setting)
        self.assertTrue(restored.success, restored.message)
        self.assertNotEqual(restored.run_id, saved.run_id)
        self.assertEqual(restored.run.verification_result["data"]["tweak_change"]["kind"], "restore")
        state = next(item for item in snapshot(self.runtime.platform_profile(), self.runtime) if item.tweak.id == "gnome-battery")
        self.assertFalse(state.restore_run_id)
        self.assertEqual(state.value, "false")

    @patch("core.tasks.tweaks.shutil.which", return_value="/usr/bin/dolphin")
    def test_new_file_and_window_tweaks_use_verified_one_step_restore(self, _which, _capability):
        cases = (
            ("gnome-files-click-policy", "single", "double", "gnome"),
            ("gnome-files-default-folder-view", "list-view", "icon-view", "gnome"),
            ("kde-dolphin-show-full-path", "true", "false", "kde"),
            ("kde-borderless-maximized-windows", "false", "true", "kde"),
        )
        for tweak_id, before, target, desktop in cases:
            with self.subTest(tweak=tweak_id):
                self.runtime._profile = profile(desktop)
                self.runtime.output[tweak_id] = f"{before}\n"
                changed = self.controller.execute(
                    BY_ID[tweak_id].action_id,
                    {"value": target},
                    confirmed=True,
                    executor=self.execute_setting,
                )
                self.assertTrue(changed.success, changed.message)
                record = changed.run.verification_result["data"]["tweak_change"]
                self.assertEqual(record["tweak_id"], tweak_id)
                self.assertEqual(record["before"], before)
                self.assertEqual(record["after"], target)

                restored = self.controller.execute(
                    f"restore-{tweak_id}",
                    {"source_run_id": changed.run_id},
                    confirmed=True,
                    executor=self.execute_setting,
                )
                self.assertTrue(restored.success, restored.message)
                self.assertEqual(restored.run.verification_result["data"]["tweak_change"]["kind"], "restore")
                state = read_tweak(BY_ID[tweak_id], self.runtime.platform_profile(), self.runtime.execute_read_only)
                self.assertEqual(state.value, before)

    def test_custom_numeric_restoration_preserves_saved_precision(self, _capability):
        self.runtime._profile = profile("kde")
        original = self.controller.execute("set-kde-animation", {"value": "0.5"}, confirmed=True, executor=self.execute_setting)
        self.assertTrue(original.success, original.message)
        restored = self.controller.execute("restore-kde-animation", {"source_run_id": original.run_id}, confirmed=True, executor=self.execute_setting)
        self.assertTrue(restored.success, restored.message)
        self.assertEqual(self.runtime.output["kde-animation"], "0.70710678\n")
        self.assertEqual(restored.run.verification_result["data"]["tweak_change"]["after"], "0.70710678")

    def test_interrupted_prepared_attempt_invalidates_previous_offer(self, _capability):
        original = self.changed()
        prepared = self.controller.confirm(self.controller.prepare("set-gnome-battery", {"value": "false"}), confirmed=True)
        self.orchestrator.interrupt_run(prepared.run_id)
        self.assertEqual(self.store.get(prepared.run_id).state, "interrupted")
        ticket = self.controller.prepare("restore-gnome-battery", {"source_run_id": original.run_id})
        self.assertTrue(ticket.blocked)

    def test_restore_ticket_revalidates_external_drift(self, _capability):
        original = self.changed()
        ticket = self.controller.prepare("restore-gnome-battery", {"source_run_id": original.run_id})
        self.runtime.output["gnome-battery"] = "false\n"
        outcome = self.controller.confirm(ticket, confirmed=True)
        self.assertFalse(outcome.success)
        self.assertEqual(outcome.status, "blocked")

    def test_failed_readback_never_succeeds_or_offers_restore(self, _capability):
        outcome = self.controller.execute("set-gnome-battery", {"value": "true"}, confirmed=True, executor=lambda *_args, **kwargs: ActionResult.ok("executed", action_id=kwargs["action_id"]))
        self.assertEqual(outcome.status, "verification_failed")
        self.assertFalse(outcome.success)
        state = next(item for item in snapshot(self.runtime.platform_profile(), self.runtime) if item.tweak.id == "gnome-battery")
        self.assertFalse(state.restore_run_id)

    def test_timeout_and_cancellation_are_durable_unsuccessful_attempts(self, _capability):
        for result in (subprocess.TimeoutExpired(["gsettings"], 1), ActionResult.fail("cancelled", exit_code=126)):
            def executor(*_args, **_kwargs):
                if isinstance(result, Exception):
                    raise result
                return result
            outcome = self.controller.execute("set-gnome-battery", {"value": "true"}, confirmed=True, executor=executor)
            self.assertFalse(outcome.success)
            self.assertIn(self.store.get(outcome.run_id).state, {"failed", "cancelled"})

    @patch.object(ActionRunStore, "save", side_effect=OSError("disk full"))
    def test_storage_failure_blocks_before_execution(self, _save, _capability):
        executor = Mock()
        outcome = self.controller.execute("set-gnome-battery", {"value": "true"}, confirmed=True, executor=executor)
        self.assertFalse(outcome.success)
        executor.assert_not_called()

    @patch.object(ActionRunStore, "save")
    def test_saved_running_reservation_survives_completion_storage_error(self, save, _capability):
        root = Path(self.temp.name)
        other_store = ActionRunStore(root / "runs.jsonl")
        other_runtime = HistoryRuntime(store=other_store)
        other = ActionCenterOrchestrator(
            facade=Mock(), runtime=other_runtime, plan_store=ActionPlanStore(root / "plans.json"),
            run_store=other_store, lease_path=root / "lease", recover_interrupted=False,
        )
        other_controller = OperationController(orchestrator=other, facade=Mock())
        self.store.path.parent.mkdir(parents=True, exist_ok=True)
        # Prepare the run before forcing the completion write to fail.
        save.side_effect = lambda run: self.store._write_unlocked([run])
        prepared = self.controller.confirm(self.controller.prepare("set-gnome-battery", {"value": "true"}), confirmed=True)
        self.assertEqual(prepared.status, "prepared")
        save.side_effect = OSError("completion storage unavailable")
        result = self.execute_setting(prepared.prepared.command, action_id="set-gnome-battery", authority="action_center")
        failed_completion = self.controller.complete(prepared, result)
        self.assertFalse(failed_completion.success)
        self.assertEqual(self.store.get(prepared.run_id).state, "running")
        executor = Mock()
        outcome = other_controller.execute("set-gnome-clock", {"value": "false"}, confirmed=True, executor=executor)
        self.assertEqual(outcome.status, "blocked")
        executor.assert_not_called()
        self.assertIn("running", outcome.message.casefold())

    def test_second_controller_cannot_mutate_during_pending_verification(self, _capability):
        root = Path(self.temp.name)
        other_store = ActionRunStore(root / "runs.jsonl")
        other_runtime = HistoryRuntime(store=other_store)
        other = ActionCenterOrchestrator(
            facade=Mock(), runtime=other_runtime, plan_store=ActionPlanStore(root / "plans.json"),
            run_store=other_store, lease_path=root / "lease", recover_interrupted=False,
        )
        other_controller = OperationController(orchestrator=other, facade=Mock())
        prepared = self.controller.confirm(self.controller.prepare("set-gnome-battery", {"value": "true"}), confirmed=True)
        result = self.execute_setting(prepared.prepared.command, action_id="set-gnome-battery", authority="action_center")
        waiting = self.controller.complete(prepared, result)
        self.assertEqual(waiting.status, "verifying")
        executor = Mock()
        blocked = other_controller.execute("set-gnome-clock", {"value": "false"}, confirmed=True, executor=executor)
        self.assertFalse(blocked.success)
        self.assertEqual(blocked.status, "blocked")
        executor.assert_not_called()
        verified = self.controller.verify(waiting)
        self.assertTrue(verified.success, verified.message)
        fresh = other_controller.confirm(other_controller.prepare("set-gnome-clock", {"value": "false"}), confirmed=True)
        self.assertEqual(fresh.status, "prepared")
        other_controller.complete(fresh, ActionResult.fail("test cleanup", exit_code=126))

    def test_corrupt_history_blocks_normal_mutation_and_startup_preserves_bytes(self, _capability):
        original = self.changed()
        path = self.store.path
        path.write_text(path.read_text() + "{invalid\n")
        saved_bytes = path.read_bytes()
        state = next(item for item in snapshot(self.runtime.platform_profile(), self.runtime) if item.tweak.id == "gnome-battery")
        self.assertFalse(state.restore_run_id)
        self.assertTrue(state.restore_message)
        self.assertEqual(path.read_bytes(), saved_bytes)
        root = Path(self.temp.name)
        restarted = ActionCenterOrchestrator(
            facade=Mock(), runtime=self.runtime, plan_store=ActionPlanStore(root / "plans.json"),
            run_store=ActionRunStore(path), lease_path=root / "lease",
        )
        executor = Mock()
        outcome = OperationController(orchestrator=restarted, facade=Mock()).execute(
            "set-gnome-battery", {"value": "false"}, confirmed=True, executor=executor,
        )
        self.assertFalse(outcome.success)
        executor.assert_not_called()
        self.assertEqual(path.read_bytes(), saved_bytes)
        for operation in (lambda: self.store.list(), lambda: self.store.save(original.run), lambda: self.store.interrupt_incomplete()):
            with self.assertRaises(ValueError):
                operation()
            self.assertEqual(path.read_bytes(), saved_bytes)

    def test_persisted_success_fields_require_literal_booleans(self, _capability):
        for execution, verification in (("false", True), (True, "false"), ("false", "false"), (1, True), (True, 1), (1, 1)):
            run = change()
            payload = {"action_run_schema_version": 4, **run.to_dict()}
            payload["execution_result"]["success"] = execution
            payload["verification_result"]["success"] = verification
            saved_bytes = (json.dumps(payload) + "\n").encode()
            self.store.path.parent.mkdir(parents=True, exist_ok=True)
            self.store.path.write_bytes(saved_bytes)
            self.runtime.output["gnome-battery"] = "true\n"
            with self.subTest(execution=execution, verification=verification):
                state = next(item for item in snapshot(self.runtime.platform_profile(), self.runtime) if item.tweak.id == "gnome-battery")
                self.assertFalse(state.restore_run_id)
                ticket = self.controller.prepare("restore-gnome-battery", {"source_run_id": run.run_id})
                self.assertTrue(ticket.blocked)
                self.assertEqual(self.store.path.read_bytes(), saved_bytes)

    def test_creation_order_blocks_restore_when_wallclock_moves_backwards(self, _capability):
        source = change(created=2)
        later = replace(source, run_id="later-attempt", state="failed", created_at=1)
        self.store.save(source)
        self.store.save(later)
        self.runtime.output["gnome-battery"] = "true\n"
        for update_source in (False, True):
            if update_source:
                self.store.save(replace(source, updated_at=3))
            with self.subTest(updated_source=update_source):
                runs = self.store.list_read_only(strict=True)
                self.assertEqual([item.run_id for item in runs], [source.run_id, later.run_id])
                state = next(item for item in snapshot(self.runtime.platform_profile(), self.runtime) if item.tweak.id == "gnome-battery")
                self.assertFalse(state.restore_run_id)
                ticket = self.controller.prepare("restore-gnome-battery", {"source_run_id": source.run_id})
                self.assertTrue(ticket.blocked)

    def test_cross_operation_lease_blocks_overlap(self, _capability):
        ticket = self.controller.prepare("set-gnome-battery", {"value": "true"})
        prepared = self.controller.confirm(ticket, confirmed=True)
        self.assertIsNotNone(prepared.prepared)
        try:
            blocked = self.controller.execute("set-gnome-clock", {"value": "false"}, confirmed=True, executor=self.execute_setting)
            self.assertFalse(blocked.success)
            self.assertEqual(blocked.status, "blocked")
        finally:
            self.controller.complete(prepared, ActionResult.fail("test interrupted", exit_code=126))


@patch("core.tasks.tweaks.kde_capability_error", return_value="")
class TestComfortRestorePresentation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_restore_button_emits_only_history_id_and_disables_while_busy(self, _capability):
        from ui.tweaks_page import TweaksPage
        page = TweaksPage(profile("gnome"))
        runtime = HistoryRuntime()
        runtime.output["gnome-battery"] = "true\n"
        runtime.runs = [change()]
        received = []
        page.restoreRequested.connect(lambda tweak_id, source_id: received.append((tweak_id, source_id)))
        try:
            page.set_states(snapshot(runtime.platform_profile(), runtime))
            button = page._restore_buttons["gnome-battery"]
            self.assertTrue(button.isEnabled())
            button.click()
            self.assertEqual(received, [("gnome-battery", "source-run")])
            page.set_busy(True)
            self.assertFalse(button.isEnabled())
            button.click()
            self.assertEqual(len(received), 1)
            page.set_error("history unreadable")
            self.assertFalse(button.isEnabled())
        finally:
            page.close()

    def test_restoration_success_requires_matching_refreshed_state(self, _capability):
        from types import SimpleNamespace
        from ui.tweaks_page import TweaksPage
        page = TweaksPage(profile("gnome"))
        runtime = HistoryRuntime()
        runtime.output["gnome-battery"] = "true\n"
        before = read_tweak(BY_ID["gnome-battery"], runtime.platform_profile(), runtime.execute_read_only)
        try:
            page.set_states((before,))
            page.set_outcome("gnome-battery", "false", SimpleNamespace(success=True, message="Verified"), restored=True)
            row = page._rows["gnome-battery"][0]
            self.assertNotEqual(row.feedback_label.property("feedbackKind"), "saved")
            page.set_states((before,))
            self.assertNotEqual(row.feedback_label.property("feedbackKind"), "saved")
            page.set_states((replace(before, value="false"),))
            self.assertEqual(row.feedback_label.property("feedbackKind"), "saved")
            self.assertIn("restored", row.feedback_label.text().casefold())
        finally:
            page.close()

    def test_blocked_restore_disables_only_affected_row_then_refreshes(self, _capability):
        from types import SimpleNamespace
        from PyQt6.QtWidgets import QWidget
        from ui.main_window_utility import MainWindowUtilityMixin
        from ui.tweaks_page import TweaksPage
        parent = QWidget()
        parent._record_global_operation_result = Mock()
        parent._start_tweak_inspection = Mock()
        page = TweaksPage(profile("gnome"))
        runtime = HistoryRuntime()
        runtime.output["gnome-battery"] = "true\n"
        runtime.runs = [change()]
        adapter = SimpleNamespace(stopped=SimpleNamespace(connect=Mock()))
        ticket = SimpleNamespace(blocked=True, plan=SimpleNamespace(policy_decision=SimpleNamespace(explanation="Setting changed outside Loofi.")))
        try:
            page.set_states(snapshot(runtime.platform_profile(), runtime))
            MainWindowUtilityMixin._show_tweak_restore_review(parent, page, "gnome-battery", ticket, adapter)
            self.assertFalse(page._restore_buttons["gnome-battery"].isEnabled())
            self.assertFalse(page._restore_buttons["gnome-battery"].property("sourceRunId"))
            self.assertFalse(page._rows["gnome-battery"][1].isEnabled())
            self.assertTrue(page._rows["gnome-clock"][1].isEnabled())
            self.assertIn("outside Loofi", page._rows["gnome-battery"][0].feedback_label.text())
            adapter.stopped.connect.call_args.args[0]()
            parent._start_tweak_inspection.assert_called_once_with(page, "gnome-battery")
        finally:
            page.close()
            parent.close()

    @patch("PyQt6.QtWidgets.QMessageBox.question")
    def test_compact_confirmation_binds_same_ticket_only_after_acceptance(self, question, _capability):
        from types import SimpleNamespace
        from PyQt6.QtWidgets import QMessageBox, QWidget
        from ui.main_window_utility import MainWindowUtilityMixin
        parent = QWidget()
        parent._record_global_operation_result = Mock()
        parent._run_tweak_restore = Mock()
        page = SimpleNamespace(set_error=Mock(), set_busy=Mock())
        adapter = SimpleNamespace(stopped=SimpleNamespace(connect=Mock()))
        ticket = SimpleNamespace(blocked=False, plan=SimpleNamespace(policy_decision=SimpleNamespace(facts={"current": "true", "requested": "false"})))
        try:
            question.return_value = QMessageBox.StandardButton.Cancel
            MainWindowUtilityMixin._show_tweak_restore_review(parent, page, "gnome-battery", ticket, adapter)
            adapter.stopped.connect.assert_not_called()
            question.return_value = QMessageBox.StandardButton.Yes
            MainWindowUtilityMixin._show_tweak_restore_review(parent, page, "gnome-battery", ticket, adapter)
            prompt = question.call_args.args[2]
            self.assertIn("true", prompt)
            self.assertIn("false", prompt)
            adapter.stopped.connect.call_args.args[0]()
            parent._run_tweak_restore.assert_called_once_with(page, "gnome-battery", ticket)
        finally:
            parent.close()
