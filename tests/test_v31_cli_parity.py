"""Tests for v31 CLI parity (tweaks and apps domain commands)."""

from __future__ import annotations

import io
import json
import unittest
from typing import Any, Sequence
from unittest.mock import patch

from cli.main import main
from core.executor.action_result import ActionResult
from core.platform.profile import DeploymentBackend, DesktopEnvironment, PlatformProfile, SessionType
from core.tasks.tweaks import TWEAKS, _read_vector

READ_OUTPUTS = {
    "gnome-color": "'prefer-dark'\n",
    "gnome-animations": "true\n",
    "gnome-text-scale": "1.25\n",
    "gnome-battery": "false\n",
    "gnome-clock": "true\n",
    "gnome-clock-format": "'24h'\n",
    "gnome-clock-weekday": "true\n",
    "gnome-button-layout": "':appmenu,close'\n",
    "gnome-tap-to-click": "true\n",
    "gnome-night-light": "false\n",
    "gnome-sound-overamp": "false\n",
    "gnome-font-antialiasing": "'rgba'\n",
    "kde-single-click": "false\n",
    "kde-double-click-interval": "400\n",
    "kde-smooth-scroll": "true\n",
    "kde-scrollbar-click": "false\n",
    "kde-color": " * BreezeDark\n * CustomTheme (current color scheme)\n * BreezeLight\n",
    "kde-animation": "0.70710678\n",
    "kde-tap-to-click": "true\n",
    "kde-night-color": "false\n",
    "power-profile": "balanced\n",
    "dnf-parallel-downloads": "max_parallel_downloads = 10\n",
}


class TestV31CliParity(unittest.TestCase):
    """Test public CLI interface for tweaks and apps domain commands."""

    def setUp(self) -> None:
        self.mock_profile = PlatformProfile(
            os_id="fedora",
            fedora_version="44",
            variant_id="workstation",
            variant_name="Fedora Workstation",
            architecture="x86_64",
            desktop=DesktopEnvironment.GNOME,
            session_type=SessionType.WAYLAND,
            deployment_backend=DeploymentBackend.DNF5,
            is_atomic=False,
            reboot_pending=False,
            package_manager_command="dnf5",
        )
        self.patchers = [
            patch("core.platform.profile.detect_platform_profile", return_value=self.mock_profile),
            patch("cli.commands.tweaks_commands.detect_platform_profile", return_value=self.mock_profile),
            patch("cli.commands.apps_commands.detect_platform_profile", return_value=self.mock_profile),
            patch("services.system.system.SystemManager.get_platform_profile", return_value=self.mock_profile),
            patch("core.executor.command_facade.CommandFacade.execute", side_effect=self._mock_command_execute),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self) -> None:
        for p in reversed(self.patchers):
            p.stop()

    def _mock_command_execute(self, vector: Sequence[str], **kwargs: Any) -> ActionResult:
        v = tuple(vector)
        action_id = kwargs.get("action_id", "")
        if v == ("powerprofilesctl", "list"):
            return ActionResult.ok("Listed", stdout="  performance:\n* balanced:\n  power-saver:\n", action_id=action_id)
        if len(v) >= 2 and v[0] == "dnf5" and "--dump-main-config" in v:
            return ActionResult.ok("Config", stdout="max_parallel_downloads = 10\n", action_id=action_id)
        if v and v[0] == "fuser":
            return ActionResult.fail("no lock", exit_code=1, action_id=action_id)
        if v and v[0] == "rpm":
            return ActionResult.fail("not installed", exit_code=1, action_id=action_id)
        if v and v[0] == "dnf5" and "repoquery" in v:
            return ActionResult.ok("Available", stdout="neovim|0.10.0-1.fc44|x86_64\n", action_id=action_id)
        if v and v[0] == "flatpak":
            if len(v) > 1 and v[1] == "info":
                return ActionResult.fail("not installed", exit_code=1, action_id=action_id)
            if len(v) > 1 and v[1] == "remote-info":
                return ActionResult.ok("Commit", stdout="mock_commit_hash\n", action_id=action_id)
        for tweak in TWEAKS:
            try:
                if tuple(_read_vector(tweak)) == v:
                    return ActionResult.ok("Read", stdout=READ_OUTPUTS.get(tweak.id, "true\n"), action_id=action_id)
            except Exception:
                pass
        return ActionResult.ok("Default ok", stdout="true\n", action_id=action_id)

    def test_tweaks_list_text_mode(self) -> None:
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = main(["tweaks", "list"])
        self.assertEqual(code, 0)
        output = buf.getvalue()
        self.assertIn("ID", output)
        self.assertIn("CURRENT", output)
        self.assertIn("STATUS", output)
        self.assertIn("dnf-parallel-downloads", output)

    def test_tweaks_list_json_mode(self) -> None:
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = main(["--json", "tweaks", "list"])
        self.assertEqual(code, 0)
        data = json.loads(buf.getvalue())
        self.assertEqual(data["schema_version"], 1)
        self.assertIn("tweaks", data)
        self.assertGreaterEqual(len(data["tweaks"]), 1)
        ids = {item["id"] for item in data["tweaks"]}
        self.assertIn("dnf-parallel-downloads", ids)

    def test_tweaks_get_text_mode(self) -> None:
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = main(["tweaks", "get", "dnf-parallel-downloads"])
        self.assertEqual(code, 0)
        output = buf.getvalue()
        self.assertIn("Setting:", output)
        self.assertIn("DNF parallel downloads", output)
        self.assertIn("Status:", output)
        self.assertIn("Choices:", output)

    def test_tweaks_get_json_mode(self) -> None:
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = main(["--json", "tweaks", "get", "dnf-parallel-downloads"])
        self.assertEqual(code, 0)
        data = json.loads(buf.getvalue())
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(data["id"], "dnf-parallel-downloads")
        self.assertEqual(data["title"], "DNF parallel downloads")
        self.assertIn("status", data)
        self.assertIn("choices", data)

    def test_tweaks_get_unknown_tweak(self) -> None:
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = main(["tweaks", "get", "nonexistent-tweak-id"])
        self.assertEqual(code, 1)
        self.assertIn("Unknown tweak", buf.getvalue())

    def test_tweaks_set_invalid_value(self) -> None:
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = main(["tweaks", "set", "dnf-parallel-downloads", "999"])
        self.assertEqual(code, 1)
        self.assertIn("Cannot apply dnf-parallel-downloads", buf.getvalue())

    def test_tweaks_set_dry_run(self) -> None:
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = main(["--dry-run", "tweaks", "set", "dnf-parallel-downloads", "10"])
        self.assertEqual(code, 0)
        self.assertIn("[dry-run]", buf.getvalue())

    def test_tweaks_restore_without_history(self) -> None:
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = main(["tweaks", "restore", "dnf-parallel-downloads"])
        self.assertEqual(code, 1)
        self.assertIn("No previous verified change", buf.getvalue())

    def test_apps_list_text_mode(self) -> None:
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = main(["apps", "list"])
        self.assertEqual(code, 0)
        output = buf.getvalue()
        self.assertIn("ID", output)
        self.assertIn("NAME", output)
        self.assertIn("CATEGORY", output)
        self.assertIn("SOURCE", output)
        self.assertIn("flatseal", output)
        self.assertIn("mission-center", output)
        self.assertIn("spotify", output)
        self.assertIn("neovim", output)

    def test_apps_list_json_mode(self) -> None:
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = main(["--json", "apps", "list"])
        self.assertEqual(code, 0)
        data = json.loads(buf.getvalue())
        self.assertEqual(data["schema_version"], 1)
        self.assertIn("applications", data)
        app_ids = {a["id"] for a in data["applications"]}
        self.assertIn("flatseal", app_ids)
        self.assertIn("mission-center", app_ids)
        self.assertIn("spotify", app_ids)
        self.assertIn("neovim", app_ids)

    def test_apps_install_unknown_app(self) -> None:
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = main(["apps", "install", "completely-unknown-app"])
        self.assertEqual(code, 1)
        self.assertIn("Unknown application", buf.getvalue())

    def test_apps_install_dry_run(self) -> None:
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = main(["--dry-run", "apps", "install", "neovim"])
        self.assertEqual(code, 0)
        self.assertIn("[dry-run]", buf.getvalue())
