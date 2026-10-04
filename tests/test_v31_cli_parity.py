"""Tests for v31 CLI parity (tweaks and apps domain commands)."""

from __future__ import annotations

import io
import json
import unittest
from typing import Any, Sequence
from unittest.mock import patch

from cli.main import main
from core.actions.contracts import ActionRun
from core.executor.action_result import ActionResult
from core.platform.profile import DeploymentBackend, DesktopEnvironment, PlatformProfile, SessionType
from core.tasks.tweaks import BY_ID, TWEAKS, _read_vector, command_for

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
    "gnome-files-click-policy": "'double'\n",
    "gnome-files-default-folder-view": "'icon-view'\n",
    "kde-single-click": "false\n",
    "kde-double-click-interval": "400\n",
    "kde-smooth-scroll": "true\n",
    "kde-scrollbar-click": "false\n",
    "kde-color": " * BreezeDark\n * CustomTheme (current color scheme)\n * BreezeLight\n",
    "kde-animation": "0.70710678\n",
    "kde-tap-to-click": "true\n",
    "kde-night-color": "false\n",
    "kde-dolphin-show-full-path": "false\n",
    "kde-borderless-maximized-windows": "false\n",
    "power-profile": "balanced\n",
    "dnf-parallel-downloads": "max_parallel_downloads = 10\n",
}


@patch("core.tasks.tweaks.kde_capability_error", return_value="")
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
        self.read_outputs = dict(READ_OUTPUTS)
        self.patchers = [
            patch("core.platform.profile.detect_platform_profile", return_value=self.mock_profile),
            patch("cli.commands.tweaks_commands.detect_platform_profile", return_value=self.mock_profile),
            patch("cli.commands.apps_commands.detect_platform_profile", return_value=self.mock_profile),
            patch("services.system.system.SystemManager.get_platform_profile", return_value=self.mock_profile),
            patch("core.executor.command_facade.CommandFacade.execute", side_effect=self._mock_command_execute),
            patch("core.tasks.tweaks.shutil.which", return_value="/usr/bin/dolphin"),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self) -> None:
        for p in reversed(self.patchers):
            p.stop()

    def _mock_command_execute(self, vector: Sequence[str], **kwargs: Any) -> ActionResult:
        v = tuple(vector)
        action_id = kwargs.get("action_id", "")
        for tweak in TWEAKS:
            if any(tuple(command_for(tweak, value)) == v for value, _label in tweak.choices):
                value = v[-1]
                quoted = tweak.id.startswith("gnome-") and value not in {"true", "false"}
                self.read_outputs[tweak.id] = f"'{value}'\n" if quoted else f"{value}\n"
                return ActionResult.ok("Wrote", action_id=action_id)
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
                    return ActionResult.ok("Read", stdout=self.read_outputs.get(tweak.id, "true\n"), action_id=action_id)
            except Exception:
                pass
        return ActionResult.ok("Default ok", stdout="true\n", action_id=action_id)

    def test_tweaks_list_text_mode(self, _capability) -> None:
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = main(["tweaks", "list"])
        self.assertEqual(code, 0)
        output = buf.getvalue()
        self.assertIn("ID", output)
        self.assertIn("CURRENT", output)
        self.assertIn("STATUS", output)
        self.assertIn("dnf-parallel-downloads", output)

    def test_tweaks_list_json_mode(self, _capability) -> None:
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

    def test_tweaks_get_text_mode(self, _capability) -> None:
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = main(["tweaks", "get", "dnf-parallel-downloads"])
        self.assertEqual(code, 0)
        output = buf.getvalue()
        self.assertIn("Setting:", output)
        self.assertIn("DNF parallel downloads", output)
        self.assertIn("Status:", output)
        self.assertIn("Choices:", output)

    def test_tweaks_get_json_mode(self, _capability) -> None:
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

    def test_tweaks_get_unknown_tweak(self, _capability) -> None:
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = main(["tweaks", "get", "nonexistent-tweak-id"])
        self.assertEqual(code, 1)
        self.assertIn("Unknown tweak", buf.getvalue())

    def test_tweaks_set_invalid_value(self, _capability) -> None:
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = main(["tweaks", "set", "dnf-parallel-downloads", "999"])
        self.assertEqual(code, 1)
        self.assertIn("Cannot apply dnf-parallel-downloads", buf.getvalue())

    def test_tweaks_set_dry_run(self, _capability) -> None:
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = main(["--dry-run", "tweaks", "set", "dnf-parallel-downloads", "10"])
        self.assertEqual(code, 0)
        self.assertIn("[dry-run]", buf.getvalue())

    def test_tweaks_restore_without_history(self, _capability) -> None:
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = main(["tweaks", "restore", "dnf-parallel-downloads"])
        self.assertEqual(code, 1)
        self.assertIn("No previous verified change", buf.getvalue())

    def test_cli_executes_and_restores_new_setting_through_action_center(self, _capability) -> None:
        tweak_id = "gnome-files-click-policy"
        output = io.StringIO()
        with patch("sys.stdout", output):
            self.assertEqual(main(["tweaks", "set", tweak_id, "single", "--yes"]), 0)
        self.assertIn("Successfully applied Open files and folders: single", output.getvalue())

        output = io.StringIO()
        with patch("sys.stdout", output):
            self.assertEqual(main(["--json", "tweaks", "get", tweak_id]), 0)
        self.assertEqual(json.loads(output.getvalue())["value"], "single")

        output = io.StringIO()
        with patch("sys.stdout", output):
            self.assertEqual(main(["tweaks", "restore", tweak_id, "--yes"]), 0)
        self.assertIn("Successfully restored Open files and folders: double", output.getvalue())

        output = io.StringIO()
        with patch("sys.stdout", output):
            self.assertEqual(main(["--json", "tweaks", "get", tweak_id]), 0)
        self.assertEqual(json.loads(output.getvalue())["value"], "double")

    def test_new_settings_have_cli_list_get_set_and_restore_parity(self, _capability) -> None:
        profiles = {
            "gnome": self.mock_profile,
            "kde": PlatformProfile(
                os_id="fedora",
                fedora_version="44",
                variant_id="kde",
                variant_name="Fedora KDE Plasma Desktop",
                architecture="x86_64",
                desktop=DesktopEnvironment.KDE,
                session_type=SessionType.WAYLAND,
                deployment_backend=DeploymentBackend.DNF5,
                is_atomic=False,
                reboot_pending=False,
                package_manager_command="dnf5",
            ),
        }
        cases = (
            ("gnome-files-click-policy", "single", "double", "gnome"),
            ("gnome-files-default-folder-view", "list-view", "icon-view", "gnome"),
            ("kde-dolphin-show-full-path", "true", "false", "kde"),
            ("kde-borderless-maximized-windows", "true", "false", "kde"),
        )
        for tweak_id, before, current, desktop in cases:
            with self.subTest(tweak=tweak_id):
                profile = profiles[desktop]
                self.mock_profile = profile
                with patch("core.platform.profile.detect_platform_profile", return_value=profile), patch(
                    "cli.commands.tweaks_commands.detect_platform_profile", return_value=profile
                ), patch("services.system.system.SystemManager.get_platform_profile", return_value=profile):
                    output = io.StringIO()
                    with patch("sys.stdout", output):
                        self.assertEqual(main(["--json", "tweaks", "list"]), 0)
                    listed = {item["id"] for item in json.loads(output.getvalue())["tweaks"]}
                    self.assertIn(tweak_id, listed)

                    output = io.StringIO()
                    with patch("sys.stdout", output):
                        self.assertEqual(main(["--json", "tweaks", "get", tweak_id]), 0)
                    self.assertEqual(json.loads(output.getvalue())["value"], current)

                    set_value = before
                    output = io.StringIO()
                    with patch("sys.stdout", output):
                        self.assertEqual(main(["--dry-run", "tweaks", "set", tweak_id, set_value]), 0)
                    self.assertIn(f"[dry-run] Would apply set-{tweak_id}", output.getvalue())

                    run = ActionRun(
                        run_id=f"source-{tweak_id}",
                        plan_id="source-plan",
                        action_id=BY_ID[tweak_id].action_id,
                        correlation_id="source-correlation",
                        parameters={"value": current},
                        affected_resources=(f"tweak:{tweak_id}",),
                        state="succeeded",
                        created_at=1.0,
                        execution_result={"success": True},
                        verification_result={"success": True, "data": {"tweak_change": {
                            "version": 1,
                            "kind": "change",
                            "tweak_id": tweak_id,
                            "before": before,
                            "after": current,
                        }}},
                    )
                    with patch("core.actions.catalog.SystemActionRuntime.tweak_runs", return_value=[run]):
                        output = io.StringIO()
                        with patch("sys.stdout", output):
                            self.assertEqual(main(["--dry-run", "tweaks", "restore", tweak_id]), 0)
                    self.assertIn(f"[dry-run] Would restore {tweak_id} to '{before}'", output.getvalue())

    def test_apps_list_text_mode(self, _capability) -> None:
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

    def test_apps_list_json_mode(self, _capability) -> None:
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

    def test_apps_install_unknown_app(self, _capability) -> None:
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = main(["apps", "install", "completely-unknown-app"])
        self.assertEqual(code, 1)
        self.assertIn("Unknown application", buf.getvalue())

    def test_apps_install_dry_run(self, _capability) -> None:
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = main(["--dry-run", "apps", "install", "neovim"])
        self.assertEqual(code, 0)
        self.assertIn("[dry-run]", buf.getvalue())
