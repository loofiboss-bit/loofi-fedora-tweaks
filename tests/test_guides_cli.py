"""Read-only CLI entry points for everyday guide discovery."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cli.main import main
from cli.parser import build_parser


class GuideCliCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        environment = {
            "XDG_CONFIG_HOME": str(root / "config"),
            "XDG_DATA_HOME": str(root / "data"),
            "XDG_CACHE_HOME": str(root / "cache"),
            "XDG_RUNTIME_DIR": str(root / "runtime"),
            "HOME": str(root / "home"),
        }
        self.environment_patch = patch.dict(os.environ, environment)
        self.environment_patch.start()
        self.stdout_patch = patch("sys.stdout", new_callable=io.StringIO)
        self.stderr_patch = patch("sys.stderr", new_callable=io.StringIO)
        self.stdout = self.stdout_patch.start()
        self.stderr = self.stderr_patch.start()

    def tearDown(self):
        self.stderr_patch.stop()
        self.stdout_patch.stop()
        self.environment_patch.stop()
        self.temp.cleanup()


class TestGuideCliGrammar(GuideCliCase):
    def test_list_and_show_parse_with_json_before_or_after_command(self):
        list_args = build_parser().parse_args(["--json", "guides", "list"])
        show_args = build_parser().parse_args(["guides", "show", "solve-a-problem", "--json"])

        self.assertEqual((list_args.command, list_args.guides_action, list_args.json), ("guides", "list", True))
        self.assertEqual((show_args.command, show_args.guides_action, show_args.guide_id, show_args.json), ("guides", "show", "solve-a-problem", True))

    def test_list_json_is_read_only_and_covers_all_four_guides(self):
        result = main(["--json", "guides", "list"])

        payload = json.loads(self.stdout.getvalue())
        self.assertEqual(result, 0)
        self.assertEqual(payload["schema_id"], "loofi.user-guides")
        self.assertEqual({item["id"] for item in payload["guides"]}, {
            "make-fedora-yours", "choose-and-manage-apps", "maintain-your-system", "solve-a-problem",
        })
        self.assertFalse((Path(os.environ["XDG_DATA_HOME"]) / "loofi-fedora-tweaks" / "guides.json").exists())

    def test_show_json_contains_inert_targets_and_does_not_run_or_save_work(self):
        result = main(["guides", "show", "solve-a-problem", "--json"])

        payload = json.loads(self.stdout.getvalue())
        self.assertEqual(result, 0)
        self.assertEqual(payload["id"], "solve-a-problem")
        self.assertEqual(len(payload["steps"]), 5)
        self.assertTrue(all(set(step["target"]) == {"route_id", "task_id", "tweak_id", "context"} for step in payload["steps"]))
        self.assertTrue(all("command" not in step["target"] for step in payload["steps"]))
        self.assertFalse((Path(os.environ["XDG_DATA_HOME"]) / "loofi-fedora-tweaks" / "guides.json").exists())

    def test_unknown_guide_returns_a_clear_error_without_state_creation(self):
        result = main(["guides", "show", "missing-guide"])

        self.assertEqual(result, 2)
        self.assertIn("Unknown guide: missing-guide", self.stderr.getvalue())
        self.assertEqual(self.stdout.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
