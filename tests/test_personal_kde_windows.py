"""Rootless contracts for personal window controls and native destinations."""
from __future__ import annotations

import tempfile
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, mock_open, patch

from core.actions.catalog import ActionCatalog
from core.actions.operation_controller import OperationController
from core.actions.orchestrator import ActionCenterOrchestrator
from core.actions.stores import ActionPlanStore, ActionRunStore
from core.catalog_models import NativeHandoffId
from core.execution_policy import execution_allowed
from core.executor.action_result import ActionResult
from core.executor.command_policy import validate_command_vector
from core.tasks.tweak_history import restoration_for
from core.tasks.tweaks import BY_ID, command_for, kde_capability_error, normalize_kwin_runtime_value, read_tweak
from core.tweak_commands import KWIN_PLACEMENT_VALUES, KWIN_RUNTIME_KEYS, KWIN_SUPPORT, kde_read_vector, valid_value
from services.desktop.native_handoff import NativeHandoffService
from test_tweaks_v30_2 import HistoryRuntime, change

NEW_IDS = ("kde-window-placement", "kde-border-snap-zone", "kde-window-snap-zone")
SCHEMA = ('<kcfg><group name="Windows"><entry name="Placement" type="Enum"><choices>'
          + ''.join(f'<choice name="Placement{value}" value="{value}"/>' for value in KWIN_PLACEMENT_VALUES)
          + '</choices></entry><entry name="BorderSnapZone" type="Int"/>'
          '<entry name="WindowSnapZone" type="Int"/></group></kcfg>').encode()


class TestPersonalWindowCatalog(unittest.TestCase):
    def test_reviewed_choices_and_exact_commands(self):
        expected = (("Placement", {"Smart", "Centered", "UnderMouse"}),
                    ("BorderSnapZone", {"0", "10", "20", "30"}),
                    ("WindowSnapZone", {"0", "10", "20", "30"}))
        for tweak_id, (key, choices) in zip(NEW_IDS, expected):
            tweak = BY_ID[tweak_id]
            self.assertEqual(set(dict(tweak.choices)), choices)
            self.assertIsNotNone(ActionCatalog().get(tweak.action_id))
            self.assertIsNotNone(ActionCatalog().get("restore-" + tweak.id))
            self.assertEqual(kde_read_vector(tweak_id)[1:7], ["--file", "kwinrc", "--group", "Windows", "--key", key])
            for value in choices:
                vector = command_for(tweak, value)
                self.assertEqual(vector, ["kwriteconfig6", "--notify", "--file", "kwinrc", "--group", "Windows", "--key", key, value])
                validate_command_vector(vector)
            for value in ("", "-1", "1001", "10.5", "--flag", "10;shutdown"):
                self.assertFalse(valid_value(tweak_id, value))

    def test_custom_values_require_only_matching_restore_authority(self):
        for tweak_id, before in ((NEW_IDS[0], "Random"), (NEW_IDS[1], "37"), (NEW_IDS[2], "1000")):
            with self.subTest(tweak_id=tweak_id):
                self.assertTrue(valid_value(tweak_id, before))
                with self.assertRaises(ValueError):
                    command_for(BY_ID[tweak_id], before)
                vector = command_for(BY_ID[tweak_id], before, restoring=True)
                validate_command_vector(vector)
                self.assertFalse(execution_allowed(vector[0], vector[1:]))
                self.assertFalse(execution_allowed(vector[0], vector[1:], authority="action_center", action_id=BY_ID[tweak_id].action_id))
                self.assertFalse(execution_allowed(vector[0], vector[1:], authority="action_center", action_id="restore-kde-animation"))
                self.assertTrue(execution_allowed(vector[0], vector[1:], authority="action_center", action_id="restore-" + tweak_id))

    @patch("core.tasks.tweaks.shutil.which", return_value="/usr/bin/tool")
    @patch("pathlib.Path.open", new_callable=mock_open, read_data=SCHEMA)
    def test_installed_enum_normalizes_numeric_runtime_and_validates_types(self, opened, which):
        for tweak_id in NEW_IDS:
            self.assertEqual(kde_capability_error(tweak_id), "")
        self.assertEqual(normalize_kwin_runtime_value(NEW_IDS[0], "5"), "Centered")
        self.assertEqual(normalize_kwin_runtime_value(NEW_IDS[0], "7"), "UnderMouse")
        self.assertEqual(normalize_kwin_runtime_value(NEW_IDS[0], "Smart"), "Smart")
        for invalid in ("10", "-1", "5.0", "0;bad", "Other"):
            self.assertEqual(normalize_kwin_runtime_value(NEW_IDS[0], invalid), "")

    @patch("core.tasks.tweaks.shutil.which", return_value="/usr/bin/tool")
    @patch("pathlib.Path.open", new_callable=mock_open, read_data=SCHEMA.replace(b'value="Smart"', b'value="Arbitrary"'))
    def test_unknown_enum_fails_closed_before_setting_read(self, opened, which):
        reader = Mock()
        state = read_tweak(BY_ID[NEW_IDS[0]], HistoryRuntime("kde").platform_profile(), reader)
        self.assertEqual(state.status, "unavailable")
        self.assertEqual(normalize_kwin_runtime_value(NEW_IDS[0], "4"), "")
        reader.assert_not_called()

    @patch("core.tasks.tweaks.shutil.which", return_value="/usr/bin/tool")
    @patch("pathlib.Path.open", side_effect=OSError)
    def test_missing_schema_blocks_window_controls(self, opened, which):
        reader = Mock()
        for tweak_id in NEW_IDS:
            self.assertEqual(read_tweak(BY_ID[tweak_id], HistoryRuntime("kde").platform_profile(), reader).status, "unavailable")
        reader.assert_not_called()


@patch("core.tasks.tweaks.kde_capability_error", return_value="")
class TestPersonalWindowLifecycle(unittest.TestCase):
    def test_custom_restore_round_trip_and_drift_block(self, capability):
        for tweak_id, before, target in ((NEW_IDS[0], "Random", "Smart"), (NEW_IDS[1], "0037", "20"), (NEW_IDS[2], "73", "30")):
            with self.subTest(tweak_id=tweak_id), tempfile.TemporaryDirectory() as directory:
                store = ActionRunStore(Path(directory) / "runs.jsonl")
                runtime = HistoryRuntime("kde", store)
                runtime.output[tweak_id] = before + "\n"
                controller = OperationController(orchestrator=ActionCenterOrchestrator(
                    catalog=ActionCatalog(), runtime=runtime, run_store=store,
                    plan_store=ActionPlanStore(Path(directory) / "plans.json")), facade=Mock())

                def write(vector, **kwargs):
                    self.assertEqual(kwargs["authority"], "action_center")
                    runtime.output[tweak_id] = vector[-1] + "\n"
                    return ActionResult.ok("Executed", exit_code=0)

                saved = controller.execute(BY_ID[tweak_id].action_id, {"value": target}, confirmed=True, executor=write)
                self.assertTrue(saved.success, saved.message)
                ticket = controller.prepare("restore-" + tweak_id, {"source_run_id": saved.run_id})
                runtime.output[tweak_id] = ("UnderMouse" if tweak_id == NEW_IDS[0] else "10") + "\n"
                self.assertFalse(controller.confirm(ticket, confirmed=True).success)
                # A fresh independent change provides a new restoration authority.
                runtime.output[tweak_id] = before + "\n"
                saved = controller.execute(BY_ID[tweak_id].action_id, {"value": target}, confirmed=True, executor=write)
                restored = controller.execute("restore-" + tweak_id, {"source_run_id": saved.run_id}, confirmed=True, executor=write)
                self.assertTrue(restored.success, restored.message)
                self.assertEqual(runtime.output[tweak_id], before + "\n")
                self.assertEqual(restored.run.verification_result["data"]["tweak_change"]["after"], before)

    @patch("core.actions.tweaks.time.sleep")
    def test_runtime_numeric_enum_success_and_failed_activation_preserve_restore(self, sleep, capability):
        for tweak_id, before, target, active in ((NEW_IDS[0], "Random", "Centered", "5"),
                                               (NEW_IDS[1], "37", "20", "20"),
                                               (NEW_IDS[2], "73", "30", "30")):
            source = change(tweak_id, before, target)
            runtime = HistoryRuntime("kde")
            runtime.runs = [source]
            runtime.output[tweak_id] = target + "\n"
            original_reader = runtime.execute_read_only
            property_name = KWIN_RUNTIME_KEYS[tweak_id]
            runtime.execute_read_only = Mock(side_effect=lambda vector, **kwargs: ActionResult.ok(
                "Read", stdout=repr((property_name + ": " + active + "\n",)))
                if tuple(vector) == KWIN_SUPPORT else original_reader(vector, **kwargs))
            definition = ActionCatalog().get("activate-kwin-tweak")
            parameters = {"tweak_id": tweak_id, "source_run_id": source.run_id}
            plan = SimpleNamespace(parameters=parameters)
            self.assertEqual(definition.verifier(source, plan, runtime).state, "succeeded")
            for output in ("malformed", repr((property_name + ": 9999\n",)), repr((property_name + ": 0\n",))):
                runtime.execute_read_only = Mock(side_effect=lambda vector, **kwargs: ActionResult.ok("Read", stdout=output)
                                                 if tuple(vector) == KWIN_SUPPORT else original_reader(vector, **kwargs))
                self.assertEqual(definition.verifier(source, plan, runtime).state, "failed")
                state = read_tweak(BY_ID[tweak_id], runtime.platform_profile(), runtime.execute_read_only)
                self.assertEqual(restoration_for(state.tweak, state, runtime.runs).source_run_id, source.run_id)
            runtime.output[tweak_id] = before + "\n"
            self.assertFalse(definition.preflight_checker(parameters, runtime).allowed)


class TestPersonalNativeHandoffs(unittest.TestCase):
    def test_fixed_modules_are_revalidated_and_similar_ids_rejected(self):
        for handoff_id, module in ((NativeHandoffId.DEFAULT_APPLICATIONS, "kcm_componentchooser"),
                                   (NativeHandoffId.AUTOSTART_SETTINGS, "kcm_autostart"),
                                   (NativeHandoffId.ICON_SETTINGS, "kcm_icons")):
            result = subprocess.CompletedProcess([], 0, module + " - Settings\n")
            runner = Mock(return_value=result)
            service = NativeHandoffService(which=Mock(return_value="/usr/bin/kcmshell6"), runner=runner)
            launch = service.prepare_launch(handoff_id)
            self.assertEqual(launch.arguments, (module,))
            self.assertTrue(all(call.args[0] == ["/usr/bin/kcmshell6", "--list"] for call in runner.call_args_list))
            result.stdout = module + "-other - Different\n"
            self.assertIsNone(service.prepare_launch(handoff_id))
            service = NativeHandoffService(which=Mock(return_value=None), runner=runner)
            self.assertFalse(service.availability(handoff_id).available)
