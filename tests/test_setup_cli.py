"""Read-only setup CLI grammar and output contracts."""
from __future__ import annotations

import argparse
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from cli.parser import build_parser
from core.tasks.setup_configurations import SetupApplication, SetupDocument
from core.tasks.tweak_profiles import TweakProfile


class SetupCliTests(unittest.TestCase):
    def test_parser_registers_list_show_and_compare_with_json(self):
        parser = build_parser()
        for action, argv in (
            ("list", ["setup", "list", "--json"]),
            ("show", ["setup", "show", "a" * 64, "--json"]),
            ("compare", ["--json", "setup", "compare", "a" * 64]),
        ):
            with self.subTest(action=action):
                args = parser.parse_args(argv)
                self.assertEqual(args.setup_action, action)
                self.assertTrue(args.json)
        with self.assertRaises(SystemExit):
            parser.parse_args(["setup", "apply", "a" * 64])

    @patch("core.tasks.setup_configurations.SetupProgressStore.list", return_value=())
    @patch("core.tasks.setup_configurations.SetupLibrary.list")
    def test_list_and_show_emit_closed_data_only_json(self, list_setups, list_progress):
        from cli.commands.setup_commands import handle_setup

        document = SetupDocument("Work", (SetupApplication("fedora", "firefox", "firefox"),),
                                 TweakProfile("Work", "kde", (("kde-single-click", "false"),)))
        identifier = document.digest
        list_setups.return_value = ((identifier, document),)
        output = Mock()
        error = Mock()
        args = argparse.Namespace(setup_action="list", json=True)
        self.assertEqual(handle_setup(args, json_output=False, output_json=output, print_fn=Mock(), error_fn=error), 0)
        self.assertEqual(output.call_args.args[0]["setups"][0]["id"], identifier)
        self.assertNotIn("command", output.call_args.args[0]["setups"][0])

        output.reset_mock()
        args = argparse.Namespace(setup_action="show", setup_id=identifier, json=True)
        self.assertEqual(handle_setup(args, json_output=False, output_json=output, print_fn=Mock(), error_fn=error), 0)
        payload = output.call_args.args[0]
        self.assertEqual(payload["document"]["applications"][0]["ref"], "firefox")
        self.assertEqual(payload["document"]["profile"]["settings"][0]["value"], "false")
        error.assert_not_called()

    @patch("cli.commands.setup_commands._compare", return_value={"schema": "loofi.setup-comparison/v1", "entries": []})
    @patch("core.tasks.setup_configurations.SetupProgressStore.list", return_value=())
    @patch("core.tasks.setup_configurations.SetupLibrary.list")
    def test_compare_delegates_to_fresh_read_only_comparison(self, list_setups, _progress, compare):
        from cli.commands.setup_commands import handle_setup

        document = SetupDocument("Work", (), TweakProfile("Work", "kde", ()))
        identifier = document.digest
        list_setups.return_value = ((identifier, document),)
        output = Mock()
        code = handle_setup(argparse.Namespace(setup_action="compare", setup_id=identifier, json=True),
                            json_output=False, output_json=output, print_fn=Mock(), error_fn=Mock())
        self.assertEqual(code, 0)
        compare.assert_called_once_with(identifier, document)
        self.assertEqual(output.call_args.args[0]["schema"], "loofi.setup-comparison/v1")

    @patch("core.tasks.setup_configurations.SetupProgressStore.list", return_value=())
    @patch("core.tasks.setup_configurations.SetupLibrary.list")
    def test_plain_output_lists_displays_and_compares_saved_setup(self, list_setups, _progress):
        from cli.commands.setup_commands import handle_setup

        document = SetupDocument("Work", (SetupApplication("fedora", "firefox", "firefox", name="Firefox"),),
                                 TweakProfile("Work", "kde", (("kde-single-click", "false"),)))
        identifier = document.digest
        list_setups.return_value = ((identifier, document),)
        printed = []
        errors = []
        with patch("cli.commands.setup_commands._compare", return_value={
            "name": "Work", "sampled_at": 123, "entries": [
                {"kind": "application", "title": "Firefox", "status": "missing", "current": "", "desired": "fedora", "message": "Not installed"}
            ],
        }):
            for action in (
                argparse.Namespace(setup_action="list", json=False),
                argparse.Namespace(setup_action="show", setup_id=identifier, json=False),
                argparse.Namespace(setup_action="compare", setup_id=identifier, json=False),
            ):
                self.assertEqual(handle_setup(action, json_output=False, output_json=Mock(),
                                              print_fn=printed.append, error_fn=errors.append), 0)

        self.assertTrue(any("Work" in line for line in printed))
        self.assertTrue(any("Firefox" in line for line in printed))
        self.assertTrue(any("Not installed" in line for line in printed))
        self.assertEqual(errors, [])

    @patch("core.tasks.setup_configurations.SetupProgressStore.list", return_value=())
    @patch("core.tasks.setup_configurations.SetupLibrary.list", return_value=())
    def test_unknown_setup_and_unreadable_library_return_errors(self, _setups, _progress):
        from cli.commands.setup_commands import handle_setup

        errors = []
        code = handle_setup(argparse.Namespace(setup_action="show", setup_id="missing", json=False),
                            json_output=False, output_json=Mock(), print_fn=Mock(), error_fn=errors.append)
        self.assertEqual(code, 2)
        self.assertIn("Unknown saved setup", errors[-1])

        with patch("core.tasks.setup_configurations.SetupLibrary.list", side_effect=ValueError("Unreadable")):
            code = handle_setup(argparse.Namespace(setup_action="list", json=False),
                                json_output=False, output_json=Mock(), print_fn=Mock(), error_fn=errors.append)
        self.assertEqual(code, 1)
        self.assertEqual(errors[-1], "Unreadable")

    def test_compare_reader_uses_local_application_and_profile_snapshots(self):
        from cli.commands.setup_commands import _compare

        document = SetupDocument("Work", (), TweakProfile("Work", "kde", (("kde-single-click", "false"),)))
        profile = object()
        comparison = Mock()
        comparison.to_dict.return_value = {"schema": "loofi.setup-comparison/v1"}
        with patch("core.actions.operation_controller.OperationController") as controller_type, \
                patch("services.system.SystemManager.get_platform_profile", return_value=profile), \
                patch("core.tasks.tweaks._profile_desktop", return_value="kde"), \
                patch("core.tasks.tweaks.visible_tweaks", return_value=(SimpleNamespace(id="kde-single-click"),)), \
                patch("core.tasks.tweaks.snapshot", return_value=()) as snapshot, \
                patch("services.software.installed_applications.InstalledApplicationService.snapshot", return_value=()) as inventory, \
                patch("core.tasks.setup_configurations.compare_setup", return_value=comparison) as compare:
            payload = _compare(document.digest, document)

        self.assertEqual(payload["schema"], "loofi.setup-comparison/v1")
        snapshot.assert_called_once_with(profile, controller_type.return_value.orchestrator.runtime,
                                        tweak_ids=("kde-single-click",))
        inventory.assert_called_once_with()
        compare.assert_called_once()


if __name__ == "__main__":
    unittest.main()
