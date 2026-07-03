"""Tests for v12 health CLI commands."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))


def _args(**kwargs):
    args = MagicMock()
    for key, value in kwargs.items():
        setattr(args, key, value)
    if "json" not in kwargs:
        args.json = False
    return args


class TestCliHealthCommands(unittest.TestCase):
    """Health CLI commands return stable JSON payloads."""

    @patch("cli.main._output_json")
    @patch("cli.main._json_output", True)
    @patch("core.observability.HealthTimelineStore")
    @patch("core.observability.HealthSnapshot")
    def test_health_snapshot_json(self, mock_snapshot_cls, mock_store_cls, mock_output_json):
        from cli.main import cmd_health

        snapshot = MagicMock()
        snapshot.to_dict.return_value = {"schema_version": 1, "fedora_target": "44"}
        mock_snapshot_cls.collect.return_value = snapshot
        store = MagicMock()
        store.append.return_value = snapshot
        store.load.return_value = [snapshot]
        mock_store_cls.return_value = store

        result = cmd_health(_args(health_action="snapshot", target="44"))

        self.assertEqual(result, 0)
        payload = mock_output_json.call_args.args[0]
        self.assertEqual(payload["schema_version"], 1)
        self.assertIn("snapshot", payload)

    @patch("cli.main._output_json")
    @patch("cli.main._json_output", True)
    @patch("core.observability.HealthTimelineStore")
    def test_health_timeline_json_empty(self, mock_store_cls, mock_output_json):
        from cli.main import cmd_health

        mock_store_cls.return_value.export.return_value = {
            "schema_version": 1,
            "count": 0,
            "trend_summary": {"summary": "No health snapshots recorded."},
            "snapshots": [],
        }

        result = cmd_health(_args(health_action="timeline", limit=10))

        self.assertEqual(result, 0)
        self.assertEqual(mock_output_json.call_args.args[0]["count"], 0)

    @patch("cli.main._output_json")
    @patch("cli.main._json_output", True)
    @patch("core.actions.ActionCenterService.recommendations_from_timeline", return_value=[])
    @patch("core.actions.ActionCenterService.candidates_from_readiness", return_value=[])
    def test_action_center_recommendations_json(self, _mock_candidates, _mock_recommendations, mock_output_json):
        from cli.main import cmd_action_center

        result = cmd_action_center(_args(action="recommendations", target="44", limit=10))

        self.assertEqual(result, 0)
        self.assertEqual(mock_output_json.call_args.args[0]["schema_version"], 1)


if __name__ == "__main__":
    unittest.main()

