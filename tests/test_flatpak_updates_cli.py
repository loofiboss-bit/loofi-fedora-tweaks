"""Read-only, installation-bound Flatpak CLI inspection."""

import argparse
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from cli.commands.update_commands import handle_updates
from cli.parser import build_parser


REF = "app/org.example.Editor/x86_64/stable"


class FlatpakUpdatesCliTests(unittest.TestCase):
    def args(self, **values):
        return argparse.Namespace(action="flatpaks", installation=None, refs=[], **values)

    def snapshot(self, *, available=True, error="", installations=(), status=None):
        payload = {"available": available, "status": status or ("available" if available else "unavailable"),
                   "checked_at": "2026-10-16T12:00:00+00:00", "error": error, "installations": []}
        return SimpleNamespace(**{**payload, "installations": installations}, to_dict=lambda: payload)

    def test_parser_keeps_full_refs_and_exact_installation(self):
        args = build_parser().parse_args(["--json", "updates", "flatpaks", "--installation", "work", "--ref", REF,
                                         "--ref", "app/org.example.Editor/aarch64/testing"])
        self.assertTrue(args.json)
        self.assertEqual(args.installation, "work")
        self.assertEqual(args.refs, [REF, "app/org.example.Editor/aarch64/testing"])

    def test_existing_update_parser_defaults_remain_supported(self):
        for action in ("check", "sources", "restart-advice", "history", "conflicts"):
            with self.subTest(action=action):
                args = build_parser().parse_args(["updates", action])
                self.assertEqual(args.action, action)

    @patch("services.software.flatpak_updates.FlatpakUpdatesService")
    def test_json_inspection_never_calls_mutation(self, service_cls):
        snapshot = self.snapshot()
        service_cls.return_value.discover.return_value = snapshot
        output, text, operation = Mock(), Mock(), Mock()
        args = self.args()
        args.installation, args.refs = "work", [REF]
        code = handle_updates(args, True, output, text, operation, Mock())
        self.assertEqual(code, 0)
        service_cls.return_value.discover.assert_called_once_with(installation="work", refs=(REF,))
        output.assert_called_once_with(snapshot.to_dict())
        operation.assert_not_called()
        service_cls.return_value.preview.assert_not_called()
        text.assert_not_called()

    @patch("services.software.flatpak_updates.FlatpakUpdatesService")
    def test_no_filters_inspects_all_scopes(self, service_cls):
        service_cls.return_value.discover.return_value = self.snapshot()
        handle_updates(self.args(), True, Mock(), Mock(), Mock(), Mock())
        service_cls.return_value.discover.assert_called_once_with(installation=None, refs=())

    @patch("services.software.flatpak_updates.FlatpakUpdatesService")
    def test_partial_results_return_nonzero_without_discarding_evidence(self, service_cls):
        snapshot = self.snapshot(status="partial")
        service_cls.return_value.discover.return_value = snapshot
        output = Mock()
        self.assertEqual(handle_updates(self.args(), True, output, Mock(), Mock(), Mock()), 1)
        output.assert_called_once_with(snapshot.to_dict())
        self.assertTrue(output.call_args.args[0]["available"])
        self.assertEqual(output.call_args.args[0]["status"], "partial")

    @patch("services.software.flatpak_updates.FlatpakUpdatesService")
    def test_unavailable_is_not_a_successful_empty_result(self, service_cls):
        service_cls.return_value.discover.return_value = self.snapshot(available=False, error="Local Flatpak support is unavailable.")
        output, operation = Mock(), Mock()
        self.assertEqual(handle_updates(self.args(), True, output, Mock(), operation, Mock()), 1)
        self.assertFalse(output.call_args.args[0]["available"])
        operation.assert_not_called()

    @patch("services.software.flatpak_updates.FlatpakUpdatesService")
    def test_text_keeps_failed_installation_and_valid_candidate_separate(self, service_cls):
        candidate = SimpleNamespace(name="Editor", ref=REF, origin="example", installed_version="1.0", available_version="2.0",
                                    installed_commit="a" * 64, expected_commit="b" * 64)
        good = SimpleNamespace(installation="user", available=True, error="", candidates=(candidate,))
        failed = SimpleNamespace(installation="work", available=False, error="Installation unavailable.", candidates=())
        service_cls.return_value.discover.return_value = self.snapshot(available=False, installations=(good, failed))
        output = Mock()
        code = handle_updates(self.args(), False, Mock(), output, Mock(), Mock())
        text = "\n".join(call.args[0] for call in output.call_args_list)
        self.assertEqual(code, 1)
        self.assertIn("Installation: user", text)
        self.assertIn("1.0 → 2.0", text)
        self.assertIn(REF, text)
        self.assertIn("Installation: work", text)
        self.assertIn("Unavailable:", text)
        self.assertIn("separate Action Center review", text)


if __name__ == "__main__":
    unittest.main()
