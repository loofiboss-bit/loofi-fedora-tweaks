"""Closed Wayfinder commands, activation authority and saved/runtime boundaries."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock, patch, mock_open

from core.actions.catalog import ActionCatalog
from core.actions.contracts import PolicyDecision
from core.actions.operation_controller import OperationController
from core.actions.orchestrator import ActionCenterOrchestrator
from core.actions.stores import ActionPlanStore, ActionRunStore
from cli.commands.tweaks_commands import handle_tweaks
from core.actions.operation_controller import OperationOutcome
from core.actions.tweak_operations import activation_parameters, activation_result, activate_verified_tweak
from core.executor.action_result import ActionResult
from core.executor.action_executor import ActionExecutor
from core.executor.command_policy import CommandValidationError, validate_command_vector
from core.execution_policy import classify_command
from core.tasks.tweak_history import restoration_for
from core.tasks.tweaks import BY_ID, TWEAKS, command_for, default_for, read_tweak, kde_capability_error
from core.tweak_commands import KWIN_RECONFIGURE, KWIN_RUNTIME_KEYS, KWIN_SUPPORT, kde_read_vector, valid_value
from test_tweaks_v30_2 import HistoryRuntime, change

NEW_IDS = (
    "kde-dolphin-editable-location", "kde-dolphin-remember-tabs", "kde-dolphin-external-folders-new-tab",
    "kde-dolphin-confirm-close-tabs", "kde-edge-tiling", "kde-focus-stealing-prevention",
    "gnome-files-editable-location", "gnome-files-date-format",
)


class TestWayfinderCatalog(unittest.TestCase):
    @patch("core.tasks.tweaks.kde_capability_error", return_value="")
    def test_defaults_commands_choices_and_metadata(self, _capability):
        self.assertEqual(len(TWEAKS), 73)
        expected_defaults = ("false", "true", "false", "true", "true", "1", "false", "simple")
        for tweak_id, default in zip(NEW_IDS, expected_defaults):
            tweak = BY_ID[tweak_id]
            with self.subTest(tweak=tweak_id):
                self.assertEqual(default_for(tweak), default)
                self.assertIn(tweak.control_kind, {"switch", "segmented", "dropdown"})
                for value, _label in tweak.choices:
                    self.assertTrue(valid_value(tweak_id, value))
                    vector = command_for(tweak, value)
                    validate_command_vector(vector)
                    self.assertEqual(classify_command(vector[0], vector[1:]), "session")
                for value in ("invalid", "-1", "5", "1;shutdown", ""):
                    self.assertFalse(valid_value(tweak_id, value))
                    with self.assertRaises(ValueError):
                        command_for(tweak, value)
                self.assertEqual(ActionCatalog().get(tweak.action_id).id, tweak.action_id)
                self.assertEqual(ActionCatalog().get("restore-" + tweak_id).id, "restore-" + tweak_id)
        self.assertEqual(BY_ID["kde-single-click"].control_kind, "segmented")
        self.assertEqual(BY_ID["gnome-files-date-format"].control_kind, "segmented")
        self.assertEqual(BY_ID["kde-focus-stealing-prevention"].control_kind, "dropdown")
        self.assertIn("Nautilus", BY_ID["gnome-files-date-format"].search_terms)
        self.assertEqual(command_for(BY_ID["gnome-files-date-format"], "detailed"), ["gsettings", "set", "org.gnome.nautilus.preferences", "date-time-format", "detailed"])
        self.assertEqual(kde_read_vector("kde-edge-tiling"), ["kreadconfig6", "--file", "kwinrc", "--group", "Windows", "--key", "ElectricBorderTiling", "--default", "true"])

    @patch("core.tasks.tweaks.shutil.which", return_value=None)
    @patch("core.tasks.tweaks.kde_capability_error", return_value="")
    def test_all_dolphin_controls_require_installed_application(self, _capability, _which):
        runtime = HistoryRuntime("kde")
        for tweak in TWEAKS:
            if tweak.id.startswith("kde-dolphin-"):
                reader = Mock()
                self.assertEqual(read_tweak(tweak, runtime.platform_profile(), reader).status, "unavailable")
                reader.assert_not_called()

    @patch("core.tasks.tweaks.kde_capability_error", return_value="")
    def test_missing_gnome_schema_or_key_never_enables_control(self, _capability):
        runtime = HistoryRuntime("gnome")
        for tweak_id in NEW_IDS[-2:]:
            reader = Mock(return_value=ActionResult.fail("No such key"))
            state = read_tweak(BY_ID[tweak_id], runtime.platform_profile(), reader)
            self.assertEqual(state.status, "unavailable")

    @patch("core.tasks.tweaks.kde_capability_error", return_value="")
    def test_dbus_policy_accepts_only_exact_shapes(self, _capability):
        for vector, operation in ((KWIN_RECONFIGURE, "session"), (KWIN_SUPPORT, "read_only")):
            validate_command_vector(vector)
            self.assertEqual(classify_command(vector[0], vector[1:]), operation)
            for invalid in (list(vector) + ["extra"], list(vector[:-1]) + ["org.kde.KWin.restart"], [vector[0], "--system", *vector[2:]]):
                with self.assertRaises(CommandValidationError):
                    validate_command_vector(invalid)
                self.assertEqual(classify_command(invalid[0], invalid[1:]), "manual_only")


class TestKWinActivation(unittest.TestCase):
    def setUp(self):
        self.runtime = HistoryRuntime("kde")
        self.source = change("kde-edge-tiling", "false", "true")
        self.runtime.runs = [self.source]
        self.runtime.output["kde-edge-tiling"] = "true\n"
        original_reader = self.runtime.execute_read_only
        self.runtime.execute_read_only = Mock(side_effect=lambda vector, **kwargs: ActionResult.ok("Runtime", stdout=repr(("electricBorderTiling: true\n",))) if tuple(vector) == KWIN_SUPPORT else original_reader(vector, **kwargs))
        self.definition = ActionCatalog().get("activate-kwin-tweak")
        self.parameters = {"tweak_id": "kde-edge-tiling", "source_run_id": self.source.run_id}
        self.plan = SimpleNamespace(parameters=self.parameters)

    @patch("core.actions.tweaks.shutil.which", return_value="/usr/bin/tool")
    @patch("core.tasks.tweaks.kde_capability_error", return_value="")
    def test_activation_is_bound_and_runtime_is_independent(self, _capability, _which):
        self.assertTrue(self.definition.preflight_checker(self.parameters, self.runtime).allowed)
        self.assertEqual(self.definition.command_renderer(self.parameters, self.runtime), list(KWIN_RECONFIGURE))
        self.assertEqual(self.definition.verifier(self.source, self.plan, self.runtime).state, "succeeded")
        self.runtime.execute_read_only.assert_any_call(KWIN_SUPPORT, action_id="activate-kwin-tweak-runtime-read", timeout=1)
        self.assertNotIn("tweak:kde-edge-tiling", self.definition.affected_resources)

    @patch("core.actions.tweaks.shutil.which", return_value="/usr/bin/tool")
    @patch("core.tasks.tweaks.kde_capability_error", return_value="")
    def test_failed_superseded_unverified_or_drifted_source_is_rejected(self, _capability, _which):
        cases = [
            [replace(self.source, state="failed")],
            [replace(self.source, execution_result={"success": False})],
            [replace(self.source, verification_result={"success": True})],
            [self.source, replace(self.source, run_id="newer")],
        ]
        for runs in cases:
            self.runtime.runs = runs
            self.assertFalse(self.definition.preflight_checker(self.parameters, self.runtime).allowed)
            with self.assertRaises(ValueError):
                self.definition.command_renderer(self.parameters, self.runtime)
        self.runtime.runs = [self.source]
        self.runtime.output["kde-edge-tiling"] = "false\n"
        self.assertFalse(self.definition.preflight_checker(self.parameters, self.runtime).allowed)

    @patch("core.actions.tweaks.shutil.which", return_value="/usr/bin/tool")
    @patch("core.tasks.tweaks.kde_capability_error", return_value="")
    def test_arbitrary_activation_parameters_fail_closed(self, _capability, _which):
        for parameters in ({**self.parameters, "value": "false"}, {**self.parameters, "source_run_id": "../bad"}, {**self.parameters, "tweak_id": "kde-focus-policy"}):
            self.assertFalse(self.definition.preflight_checker(parameters, self.runtime).allowed)

    @patch("core.actions.tweaks.shutil.which", return_value=None)
    @patch("core.tasks.tweaks.kde_capability_error", return_value="")
    def test_missing_tools_keeps_saved_restore_authority(self, _capability, _which):
        self.assertFalse(self.definition.preflight_checker(self.parameters, self.runtime).allowed)
        state = read_tweak(BY_ID["kde-edge-tiling"], self.runtime.platform_profile(), self.runtime.execute_read_only)
        self.assertEqual(restoration_for(state.tweak, state, self.runtime.runs).source_run_id, self.source.run_id)

    @patch("core.tasks.tweaks.kde_capability_error", return_value="")
    @patch("core.actions.tweaks.time.sleep")
    def test_runtime_failures_preserve_restore(self, _sleep, _capability):
        saved_reader = self.runtime.execute_read_only
        for result in (
            ActionResult.fail("No DBus"), ActionResult.ok("Read", stdout="malformed"),
            ActionResult.ok("Read", stdout=repr(("electricBorderTiling: false\n",))),
            ActionResult.ok("Read", stdout=repr(("electricBorderTiling: true\nelectricBorderTiling: true\n",))),
        ):
            self.runtime.execute_read_only = Mock(side_effect=lambda vector, **kwargs: result if tuple(vector) == KWIN_SUPPORT else saved_reader(vector, **kwargs))
            self.assertEqual(self.definition.verifier(self.source, self.plan, self.runtime).state, "failed")
            activation = replace(self.source, run_id="activation", action_id="activate-kwin-tweak", affected_resources=self.definition.affected_resources, state="verification_failed")
            state = read_tweak(BY_ID["kde-edge-tiling"], self.runtime.platform_profile(), self.runtime.execute_read_only)
            self.assertEqual(restoration_for(state.tweak, state, [self.source, activation]).source_run_id, self.source.run_id)

    @patch("core.actions.tweaks.shutil.which", return_value="/usr/bin/tool")
    @patch("core.tasks.tweaks.kde_capability_error", return_value="")
    def test_successful_restore_can_activate(self, _capability, _which):
        record = {"version": 1, "kind": "restore", "tweak_id": "kde-edge-tiling", "before": "true", "after": "false", "source_run_id": "original"}
        restored = replace(self.source, action_id="restore-kde-edge-tiling", parameters={"source_run_id": "original"}, verification_result={"success": True, "data": {"tweak_change": record}})
        self.runtime.runs = [restored]
        self.runtime.output["kde-edge-tiling"] = "false\n"
        self.assertTrue(self.definition.preflight_checker(self.parameters, self.runtime).allowed)

    @patch("core.tasks.tweaks.kde_capability_error", return_value="")
    def test_shared_helper_reports_saved_success_when_activation_fails(self, _capability):
        saved = OperationOutcome("set-kde-edge-tiling", "succeeded", "verify", "Saved", run_id="source-run")
        failed = OperationOutcome("activate-kwin-tweak", "failed", "run", "No DBus")
        self.assertEqual(activation_parameters(saved), self.parameters)
        result = activation_result(saved, failed)
        self.assertTrue(result.saved_verified)
        self.assertFalse(result.session_verified)
        self.assertIn("unverified", result.message)
        self.assertIsNone(activation_parameters(replace(saved, status="verification_failed")))
        controller = Mock()
        controller.prepare.return_value = SimpleNamespace(blocked=True, plan=SimpleNamespace(policy_decision=PolicyDecision(False, "missing", "Tool unavailable")))
        result = activate_verified_tweak(controller, saved)
        self.assertTrue(result.saved_verified)
        controller.run.assert_not_called()

    @patch("core.tasks.tweaks.kde_capability_error", return_value="")
    def test_activation_exception_does_not_erase_successful_saved_change(self, _capability):
        saved = OperationOutcome("set-kde-edge-tiling", "succeeded", "verify", "Saved", run_id="source-run")
        for error in (OSError("Unavailable history"), RuntimeError("DBus unavailable"), ValueError("Rejected")):
            controller = Mock()
            controller.prepare.side_effect = error
            result = activate_verified_tweak(controller, saved)
            self.assertTrue(result.saved_verified)
            self.assertFalse(result.session_verified)
            self.assertIn("unverified", result.message)
            self.assertTrue(saved.success)


    @patch("core.tasks.tweaks.kde_capability_error", return_value="")
    @patch("core.actions.tweaks.time.sleep")
    @patch("core.actions.tweaks.time.monotonic", return_value=0)
    def test_old_then_current_runtime_value_succeeds_without_write_retry(self, _clock, sleep, _capability):
        saved_reader = self.runtime.execute_read_only
        outputs = iter(("false", "true"))
        self.runtime.execute_read_only = Mock(side_effect=lambda vector, **kwargs: ActionResult.ok("Runtime", stdout=repr(("electricBorderTiling: " + next(outputs) + "\n",))) if tuple(vector) == KWIN_SUPPORT else saved_reader(vector, **kwargs))
        result = self.definition.verifier(self.source, self.plan, self.runtime)
        self.assertEqual(result.state, "succeeded")
        calls = [call for call in self.runtime.execute_read_only.call_args_list if tuple(call.args[0]) == KWIN_SUPPORT]
        self.assertEqual(len(calls), 2)
        sleep.assert_called_once_with(0.1)

    @patch("core.tasks.tweaks.kde_capability_error", return_value="")
    @patch("core.actions.tweaks.time.sleep")
    @patch("core.actions.tweaks.time.monotonic", return_value=0)
    def test_unmatched_runtime_value_stops_after_three_reads(self, _clock, sleep, _capability):
        saved_reader = self.runtime.execute_read_only
        self.runtime.execute_read_only = Mock(side_effect=lambda vector, **kwargs: ActionResult.ok("Runtime", stdout=repr(("electricBorderTiling: false\n",))) if tuple(vector) == KWIN_SUPPORT else saved_reader(vector, **kwargs))
        result = self.definition.verifier(self.source, self.plan, self.runtime)
        self.assertEqual(result.state, "failed")
        self.assertIn("did not match", result.message)
        calls = [call for call in self.runtime.execute_read_only.call_args_list if tuple(call.args[0]) == KWIN_SUPPORT]
        self.assertEqual(len(calls), 3)
        self.assertEqual(sleep.call_count, 2)

    @patch("core.tasks.tweaks.kde_capability_error", return_value="")
    @patch("core.actions.tweaks.time.sleep")
    @patch("core.actions.tweaks.time.monotonic", side_effect=(0, 0.95))
    def test_runtime_poll_respects_deadline(self, _clock, sleep, _capability):
        saved_reader = self.runtime.execute_read_only
        self.runtime.execute_read_only = Mock(side_effect=lambda vector, **kwargs: ActionResult.ok("Runtime", stdout=repr(("electricBorderTiling: false\n",))) if tuple(vector) == KWIN_SUPPORT else saved_reader(vector, **kwargs))
        self.assertEqual(self.definition.verifier(self.source, self.plan, self.runtime).state, "failed")
        calls = [call for call in self.runtime.execute_read_only.call_args_list if tuple(call.args[0]) == KWIN_SUPPORT]
        self.assertEqual(len(calls), 1)
        sleep.assert_not_called()

    @patch("core.tasks.tweaks.kde_capability_error", return_value="")
    @patch("core.actions.tweaks.time.sleep")
    def test_tool_and_parse_failures_never_poll(self, sleep, _capability):
        saved_reader = self.runtime.execute_read_only
        for result in (ActionResult.fail("DBus unavailable"), ActionResult.ok("Read", stdout="truncated"), ActionResult.ok("Read", stdout=repr(("electricBorderTiling: invalid\n",)))):
            self.runtime.execute_read_only = Mock(side_effect=lambda vector, **kwargs: result if tuple(vector) == KWIN_SUPPORT else saved_reader(vector, **kwargs))
            self.assertEqual(self.definition.verifier(self.source, self.plan, self.runtime).state, "failed")
            calls = [call for call in self.runtime.execute_read_only.call_args_list if tuple(call.args[0]) == KWIN_SUPPORT]
            self.assertEqual(len(calls), 1)
            sleep.assert_not_called()


class TestWayfinderSetRestoreAndCLI(unittest.TestCase):
    @patch("core.tasks.tweaks.shutil.which", return_value="/usr/bin/dolphin")
    @patch("core.tasks.tweaks.kde_capability_error", return_value="")
    def test_each_added_control_independently_verifies_then_restores(self, _capability, _which):
        for tweak_id in NEW_IDS:
            tweak = BY_ID[tweak_id]
            desktop = tweak.desktop
            before, target = (value for value, _label in tweak.choices[:2])
            with self.subTest(tweak=tweak_id), tempfile.TemporaryDirectory() as directory:
                store = ActionRunStore(Path(directory) / "runs.jsonl")
                runtime = HistoryRuntime(desktop, store)
                runtime.output[tweak_id] = before + "\n"
                controller = OperationController(orchestrator=ActionCenterOrchestrator(catalog=ActionCatalog(), runtime=runtime, run_store=store, plan_store=ActionPlanStore(Path(directory) / "plans.json")), facade=Mock())

                def write(vector, **kwargs):
                    self.assertEqual(kwargs["authority"], "action_center")
                    runtime.output[tweak_id] = vector[-1] + "\n"
                    return ActionResult.ok("Written", exit_code=0)

                changed = controller.execute(tweak.action_id, {"value": target}, confirmed=True, executor=write)
                self.assertTrue(changed.success, changed.message)
                self.assertEqual(changed.run.verification_result["data"]["tweak_change"]["before"], before)
                state = read_tweak(tweak, runtime.platform_profile(), runtime.execute_read_only)
                self.assertEqual(restoration_for(tweak, state, runtime.tweak_runs()).source_run_id, changed.run_id)
                runtime.output[tweak_id] = before + "\n"
                blocked = ActionCatalog().get("restore-" + tweak_id).preflight_checker({"source_run_id": changed.run_id}, runtime)
                self.assertFalse(blocked.allowed)
                runtime.output[tweak_id] = target + "\n"
                restored = controller.execute("restore-" + tweak_id, {"source_run_id": changed.run_id}, confirmed=True, executor=write)
                self.assertTrue(restored.success, restored.message)
                self.assertEqual(read_tweak(tweak, runtime.platform_profile(), runtime.execute_read_only).value, before)

    @patch("core.tasks.tweaks.shutil.which", return_value="/usr/bin/dolphin")
    @patch("cli.commands.tweaks_commands.OperationController")
    @patch("cli.commands.tweaks_commands.SystemActionRuntime")
    @patch("cli.commands.tweaks_commands.detect_platform_profile")
    @patch("core.tasks.tweaks.kde_capability_error", return_value="")
    def test_list_get_set_restore_public_cli_parity(self, _capability, detect, runtime_factory, controller_factory, _which):
        controller_factory.return_value.prepare.return_value = SimpleNamespace(blocked=False)
        for tweak_id in NEW_IDS:
            tweak = BY_ID[tweak_id]
            runtime = HistoryRuntime(tweak.desktop)
            runtime.facade = Mock()
            before, after = (value for value, _label in tweak.choices[:2])
            runtime.output[tweak_id] = after + "\n"
            runtime.runs = [change(tweak_id, before, after)]
            runtime_factory.return_value = runtime
            detect.return_value = runtime.platform_profile()
            serialized, printed = Mock(), Mock()
            for action in ("list", "get", "set", "restore"):
                args = SimpleNamespace(tweaks_action=action, tweak_id=tweak_id, value=before, desktop="all", yes=True)
                code = handle_tweaks(args, True, serialized, printed, dry_run=True)
                self.assertEqual(code, 0)
                if action == "list":
                    self.assertIn(tweak_id, {row["id"] for row in serialized.call_args.args[0]["tweaks"]})
                elif action == "get":
                    self.assertEqual(serialized.call_args.args[0]["value"], after)
                else:
                    parameters = {"value": before} if action == "set" else {"source_run_id": "source-run"}
                    controller_factory.return_value.prepare.assert_called_with(("set-" if action == "set" else "restore-") + tweak_id, parameters)
            controller_factory.return_value.run.assert_not_called()


class TestKWinActivationLifecycle(unittest.TestCase):
    @patch("core.actions.tweaks.shutil.which", return_value="/usr/bin/tool")
    @patch("core.tasks.tweaks.kde_capability_error", return_value="")
    def test_each_runtime_setting_activates_after_change_and_restore(self, _capability, _which):
        for tweak_id, property_name in KWIN_RUNTIME_KEYS.items():
            tweak = BY_ID[tweak_id]
            before, target = (value for value, _label in tweak.choices[:2])
            with self.subTest(tweak=tweak_id), tempfile.TemporaryDirectory() as directory:
                store = ActionRunStore(Path(directory) / "runs.jsonl")
                runtime = HistoryRuntime("kde", store)
                runtime.output[tweak_id] = before + "\n"
                original_reader = runtime.execute_read_only
                runtime.execute_read_only = lambda vector, **kwargs: ActionResult.ok("Runtime", stdout=repr((property_name + ": " + runtime.output[tweak_id],))) if tuple(vector) == KWIN_SUPPORT else original_reader(vector, **kwargs)
                controller = OperationController(orchestrator=ActionCenterOrchestrator(catalog=ActionCatalog(), runtime=runtime, run_store=store, plan_store=ActionPlanStore(Path(directory) / "plans.json")), facade=Mock())

                def write(vector, **kwargs):
                    if kwargs["action_id"] == "activate-kwin-tweak":
                        self.assertEqual(tuple(vector), KWIN_RECONFIGURE)
                    else:
                        runtime.output[tweak_id] = vector[-1] + "\n"
                    return ActionResult.ok("Executed", exit_code=0)

                source = controller.execute(tweak.action_id, {"value": target}, confirmed=True, executor=write)
                self.assertTrue(source.success, source.message)
                activated = controller.execute("activate-kwin-tweak", activation_parameters(source), confirmed=True, executor=write)
                self.assertTrue(activated.success, activated.message)
                state = read_tweak(tweak, runtime.platform_profile(), runtime.execute_read_only)
                self.assertEqual(restoration_for(tweak, state, runtime.tweak_runs()).source_run_id, source.run_id)
                restored = controller.execute("restore-" + tweak_id, {"source_run_id": source.run_id}, confirmed=True, executor=write)
                self.assertTrue(restored.success, restored.message)
                activated = controller.execute("activate-kwin-tweak", activation_parameters(restored), confirmed=True, executor=write)
                self.assertTrue(activated.success, activated.message)
                self.assertEqual(read_tweak(tweak, runtime.platform_profile(), runtime.execute_read_only).value, before)


class TestInstalledKDECapabilities(unittest.TestCase):
    @patch("core.tasks.tweaks.Path.open", new_callable=mock_open, read_data=b'<kcfg xmlns="http://www.kde.org/standards/kcfg/1.0"><group name="General"><entry name="EditableUrl" type="Bool"/></group></kcfg>')
    @patch("core.tasks.tweaks.shutil.which", return_value="/usr/bin/tool")
    def test_only_reviewed_group_and_key_grant_availability(self, _which, opened):
        self.assertEqual(kde_capability_error("kde-dolphin-editable-location"), "")
        opened.assert_called_once_with("rb")
        opened().read.assert_called_once_with(256 * 1024 + 1)
        error = kde_capability_error("kde-dolphin-remember-tabs")
        self.assertIn("General/RememberOpenedTabs", error)

    @patch("core.tasks.tweaks.Path.open", new_callable=mock_open, read_data=b'<kcfg><group name="Windows"><entry name="FocusStealingPreventionLevel" type="Int"/><entry name="ElectricBorderTiling" type="Bool"/><entry name="BorderlessMaximizedWindows" type="Bool"/></group></kcfg>')
    @patch("core.tasks.tweaks.shutil.which", return_value="/usr/bin/tool")
    def test_kwin_supports_all_three_reviewed_keys(self, _which, _opened):
        for tweak_id in KWIN_RUNTIME_KEYS:
            self.assertEqual(kde_capability_error(tweak_id), "")

    @patch("core.tasks.tweaks.Path.open", side_effect=FileNotFoundError)
    @patch("core.tasks.tweaks.shutil.which", return_value="/usr/bin/tool")
    def test_missing_schema_is_unavailable_without_probing_saved_value(self, _which, _opened):
        runtime = HistoryRuntime("kde")
        reader = Mock()
        for tweak_id in ("kde-dolphin-show-full-path", "kde-edge-tiling"):
            state = read_tweak(BY_ID[tweak_id], runtime.platform_profile(), reader)
            self.assertEqual(state.status, "unavailable")
            self.assertIn("settings schema is unavailable", state.message)
        reader.assert_not_called()

    @patch("core.tasks.tweaks.Path.open")
    @patch("core.tasks.tweaks.shutil.which", return_value=None)
    def test_missing_program_is_concrete_and_does_not_read_schema(self, _which, opened):
        self.assertEqual(kde_capability_error("kde-dolphin-show-full-path"), "Dolphin is not installed.")
        self.assertEqual(kde_capability_error("kde-borderless-maximized-windows"), "KWin is not installed.")
        opened.assert_not_called()

    @patch("core.tasks.tweaks.Path.open")
    @patch("core.tasks.tweaks.shutil.which")
    def test_missing_config_tool_is_unavailable(self, which, opened):
        which.side_effect = lambda name: None if name == "kwriteconfig6" else "/usr/bin/tool"
        self.assertIn("kwriteconfig6", kde_capability_error("kde-dolphin-show-full-path"))
        opened.assert_not_called()

    @patch("core.tasks.tweaks.Path.open", new_callable=mock_open)
    @patch("core.tasks.tweaks.shutil.which", return_value="/usr/bin/tool")
    def test_invalid_oversized_or_wrong_group_type_schema_fails_closed(self, _which, opened):
        for payload in (b"not XML", b"x" * (256 * 1024 + 1), b'<kcfg><group name="Other"><entry name="EditableUrl" type="Bool"/></group></kcfg>', b'<kcfg><group name="General"><entry name="EditableUrl" type="String"/></group></kcfg>'):
            opened().read.return_value = payload
            self.assertTrue(kde_capability_error("kde-dolphin-editable-location"))


class TestKWinSupportOutputBoundary(unittest.TestCase):
    @patch("core.executor.action_executor.subprocess.run")
    def test_only_exact_support_read_retains_long_output_in_memory(self, run):
        payload = repr(("Support details: " + "x" * 6500 + "\nelectricBorderTiling: true\n",))
        run.return_value = SimpleNamespace(returncode=0, stdout=payload, stderr="")
        executor = ActionExecutor()
        result = executor._execute_subprocess(list(KWIN_SUPPORT), timeout=8, action_id="read", env=None)
        self.assertTrue(result.success)
        self.assertEqual(result.stdout, payload)
        self.assertEqual(len(result.to_dict()["stdout"]), 4000)
        self.assertEqual(result.message, "KWin runtime information read.")
        ordinary = executor._execute_subprocess(["echo", "test"], timeout=8, action_id="read", env=None)
        self.assertEqual(len(ordinary.stdout), 4000)
        wrapped = executor._execute_subprocess(["flatpak-spawn", "--host", *KWIN_SUPPORT], timeout=8, action_id="read", env=None)
        self.assertEqual(wrapped.stdout, payload)

    @patch("core.executor.action_executor.subprocess.run")
    def test_oversized_support_information_fails_without_retaining_details(self, run):
        run.return_value = SimpleNamespace(returncode=0, stdout="x" * (1024 * 1024 + 1), stderr="")
        result = ActionExecutor()._execute_subprocess(list(KWIN_SUPPORT), timeout=8, action_id="read", env=None)
        self.assertFalse(result.success)
        self.assertEqual(result.stdout, "")
        self.assertIn("exceeded", result.message)

    @patch("core.tasks.tweaks.kde_capability_error", return_value="")
    @patch("core.executor.action_executor.subprocess.run")
    def test_runtime_verifier_parses_complete_long_support_information(self, run, _capability):
        runtime = HistoryRuntime("kde")
        runtime.runs = [change("kde-edge-tiling", "false", "true")]
        runtime.output["kde-edge-tiling"] = "true\n"
        original = runtime.execute_read_only
        payload = repr(("Support details: " + "x" * 6500 + "\nelectricBorderTiling: true\n",))
        run.return_value = SimpleNamespace(returncode=0, stdout=payload, stderr="")
        runtime.execute_read_only = lambda vector, **kwargs: ActionExecutor()._execute_subprocess(list(vector), timeout=kwargs["timeout"], action_id=kwargs["action_id"], env=None) if tuple(vector) == KWIN_SUPPORT else original(vector, **kwargs)
        plan = SimpleNamespace(parameters={"tweak_id": "kde-edge-tiling", "source_run_id": "source-run"})
        result = ActionCatalog().get("activate-kwin-tweak").verifier(runtime.runs[0], plan, runtime)
        self.assertEqual(result.state, "succeeded")
        self.assertNotIn("Support details", str(result.data))

    def test_activation_failure_shows_verification_reason(self):
        saved = OperationOutcome("set-kde-edge-tiling", "succeeded", "verify", "Saved", run_id="source-run")
        failed = OperationOutcome("activate-kwin-tweak", "verification_failed", "verify", "Operation state updated.", result=ActionResult.fail("KWin runtime information could not be parsed safely."))
        message = activation_result(saved, failed).message
        self.assertIn("could not be parsed safely", message)
        self.assertNotIn("Operation state updated", message)
        run = replace(change("kde-edge-tiling"), verification_result={"success": False, "message": "KWin active value did not match."})
        failed = replace(failed, result=None, run=run)
        self.assertIn("active value did not match", activation_result(saved, failed).message)
