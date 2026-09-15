"""v29 compatibility behavior for the Activity/Changes CLI surfaces."""

from __future__ import annotations

import argparse
from unittest.mock import patch


class TestChangesActivityAlias:
    """History commands use Activity while mutation verbs stay compatible."""

    @patch("cli.main.cmd_activity", return_value=0)
    def test_changes_list_delegates_to_activity(self, cmd_activity):
        from cli.main import cmd_changes

        result = cmd_changes(argparse.Namespace(changes_action="list", limit=25))

        assert result == 0
        assert cmd_activity.call_args.args[0].activity_action == "list"

    @patch("cli.main.cmd_activity", return_value=0)
    def test_changes_show_delegates_to_activity(self, cmd_activity):
        from cli.main import cmd_changes

        result = cmd_changes(argparse.Namespace(changes_action="show", id="event-1"))

        assert result == 0
        forwarded = cmd_activity.call_args.args[0]
        assert forwarded.activity_action == "show"
        assert forwarded.event_id == "event-1"
