"""Compatibility contract for the domain-separated public CLI parser."""

import argparse
import hashlib
import json
import unittest

from cli.parser import build_parser


EXPECTED_TOP_LEVEL_COMMANDS = (
    "info",
    "check",
    "updates",
    "troubleshoot",
    "changes",
    "activity",
    "doctor",
    "support-bundle",
)
EXPECTED_PARSER_SNAPSHOT_SHA256 = "1ab05c5b546a1d8440385f58cd134dfcfe59d48b3d80625ba91a31a625339e3a"


def _normalize(value):
    """Return stable JSON-compatible argparse metadata."""
    if value is argparse.SUPPRESS:
        return "<SUPPRESS>"
    if isinstance(value, dict):
        return list(value)
    if isinstance(value, type):
        return value.__name__
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    return value


def _parser_snapshot(parser):
    """Capture ordered commands, arguments, defaults, choices, and help."""
    actions = []
    for action in parser._actions:
        record = {
            "kind": type(action).__name__,
            "dest": action.dest,
            "options": list(action.option_strings),
            "nargs": _normalize(action.nargs),
            "default": _normalize(action.default),
            "required": action.required,
            "choices": _normalize(action.choices),
            "const": _normalize(action.const),
            "type": getattr(action.type, "__name__", None),
            "help": _normalize(action.help),
        }
        if isinstance(action, argparse._SubParsersAction):
            record["commands"] = [(name, _parser_snapshot(child)) for name, child in action.choices.items()]
        actions.append(record)
    return actions


def _top_level_commands(parser):
    """Return public commands in displayed help order."""
    action = next(item for item in parser._actions if isinstance(item, argparse._SubParsersAction))
    return tuple(action.choices)


class TestCliParserContract(unittest.TestCase):
    """Protect command order and the complete public argparse grammar."""

    def test_top_level_command_order_is_compatible(self):
        self.assertEqual(_top_level_commands(build_parser()), EXPECTED_TOP_LEVEL_COMMANDS)

    def test_complete_parser_snapshot_is_compatible(self):
        payload = json.dumps(_parser_snapshot(build_parser()), ensure_ascii=True, separators=(",", ":"))
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        self.assertEqual(digest, EXPECTED_PARSER_SNAPSHOT_SHA256, payload)

    def test_global_json_timeout_and_dry_run_defaults_are_preserved(self):
        defaults = build_parser().parse_args(["info"])
        configured = build_parser().parse_args(["--json", "--timeout", "12", "--dry-run", "info"])

        self.assertEqual((defaults.json, defaults.timeout, defaults.dry_run), (False, 300, False))
        self.assertEqual((configured.json, configured.timeout, configured.dry_run), (True, 12, True))

    def test_nested_changes_and_troubleshoot_arguments_are_preserved(self):
        changes = build_parser().parse_args(
            ["changes", "apply", "install-application", "--param", "package-id=org.example.App", "--yes"]
        )
        troubleshoot = build_parser().parse_args(["troubleshoot", "compare", "before", "after"])

        self.assertEqual(
            (changes.changes_action, changes.target, changes.release_target, changes.param, changes.yes),
            ("apply", "install-application", "44", ["package-id=org.example.App"], True),
        )
        self.assertEqual((troubleshoot.troubleshoot_action, troubleshoot.session_id, troubleshoot.followup_id), ("compare", "before", "after"))


if __name__ == "__main__":
    unittest.main()
