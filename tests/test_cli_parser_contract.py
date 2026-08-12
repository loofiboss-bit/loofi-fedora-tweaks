"""Compatibility contract for the domain-separated public CLI parser."""

import argparse
import hashlib
import json
import unittest

from cli.parser import build_parser


EXPECTED_TOP_LEVEL_COMMANDS = (
    "info", "health", "maintenance", "activity", "troubleshoot", "disk", "processes", "temperature", "netmon",
    "cleanup", "tweak", "advanced", "network", "doctor", "hardware", "plugins", "api-key", "plugin-marketplace",
    "support-bundle", "state", "readiness", "action-center", "fedora44-readiness", "vm", "vfio", "mesh", "teleport",
    "ai-models", "preset", "focus-mode", "security-audit", "profile", "health-history", "tuner", "snapshot", "logs",
    "service", "package", "firewall", "bluetooth", "storage", "self-update", "agent", "audit-log", "updates", "extension",
    "flatpak-manage", "boot", "display", "backup", "run",
)
EXPECTED_PARSER_SNAPSHOT_SHA256 = "45089eae7e6178ae57f65d8298cb5a0fc9618c61337fde89ee9f3a3957e29293"


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

    def test_nested_action_center_and_troubleshoot_arguments_are_preserved(self):
        action = build_parser().parse_args(
            ["action-center", "plan", "install-application", "--source", "flatpak", "--package-id", "org.example.App"]
        )
        troubleshoot = build_parser().parse_args(["troubleshoot", "compare", "before", "after"])

        self.assertEqual((action.action, action.action_id, action.source, action.package_id), ("plan", "install-application", "flatpak", "org.example.App"))
        self.assertEqual((troubleshoot.troubleshoot_action, troubleshoot.session_id, troubleshoot.followup_id), ("compare", "before", "after"))


if __name__ == "__main__":
    unittest.main()
