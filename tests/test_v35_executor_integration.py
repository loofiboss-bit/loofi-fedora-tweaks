"""Exercise real policy/facade boundaries while mocking only process execution."""
import json
import hashlib
import io
import subprocess
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core.actions.catalog import SystemActionRuntime
from core.execution_policy import classify_command, execution_allowed
from core.executor.action_executor import ActionExecutor
from core.executor.command_facade import CommandFacade
from services.software.rpm_transactions import HELPER, RpmTransactionPreview, RpmTransactionService, evidence_digest, verify_preview


def snapshot():
    installed = tuple(f"unrelated-{index}-0:1-1.noarch" for index in range(1000))
    item = {"action": "Install", "name": "fixture", "nevra": "fixture-0:1-1.noarch", "repo_id": "fixture", "checksum": "a" * 64}
    preview = RpmTransactionPreview(True, "", packages=("fixture",), installed=installed,
                                    operations=(item,), repository_digest="b" * 64)
    return replace(preview, digest=evidence_digest(preview.to_dict()))


class ExecutorIntegrationTests(unittest.TestCase):
    @patch("services.software.application_discovery.rpm_catalog_paths", return_value=(Path("/fixture/catalog.xml"),))
    @patch("builtins.open")
    @patch("core.actions.catalog.SystemActionRuntime.package_manager", return_value="dnf5")
    @patch("core.executor.action_executor.ActionExecutor._log_action")
    @patch("core.executor.action_executor.subprocess.run")
    def test_metadata_cache_verification_crosses_real_read_only_boundary(self, run, _log, _manager, opener, _paths):
        from core.actions.application_metadata import _verify
        opener.side_effect = lambda *_args, **_kwargs: io.BytesIO(
            b'<components><component type="desktop-application"><id>org.example.Editor</id>'
            b'<name>Editor</name><pkgname>editor</pkgname></component></components>')
        repository_digest = "b" * 64
        parameters = {"source": "fedora"}
        plan = SimpleNamespace(parameters=parameters, policy_decision=SimpleNamespace(facts={
            "metadata_evidence_version": 1, "metadata_source": parameters,
            "configured_identity": hashlib.sha256(repository_digest.encode()).hexdigest(),
        }))
        run.side_effect = (
            subprocess.CompletedProcess([], 0, json.dumps({"available": True, "enabled_count": 1, "repository_digest": repository_digest}), ""),
            subprocess.CompletedProcess([], 0, "fedora-release\\tfedora\\n", ""),
        )
        runtime = SystemActionRuntime(CommandFacade())
        result = _verify(None, plan, runtime)
        self.assertEqual(result.state, "succeeded")
        opener.assert_called_once_with(Path("/fixture/catalog.xml"), "rb")
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args.args[0][:3], ["dnf5", "--cacheonly", "repoquery"])
        self.assertFalse(execution_allowed("dnf5", ["--cacheonly", "install", "fixture"]))

    @patch("services.software.rpm_transactions.helper_command", return_value=HELPER)
    @patch("core.executor.action_executor.ActionExecutor._log_action")
    @patch("core.executor.action_executor.subprocess.run")
    def test_large_rpm_preview_survives_real_facade_without_persisting_full_output(self, run, _log, _helper):
        expected = snapshot()
        payload = json.dumps(expected.to_dict())
        self.assertGreater(len(payload), 4000)
        run.return_value = subprocess.CompletedProcess([], 0, payload, "")
        runtime = SystemActionRuntime(CommandFacade())
        observed = RpmTransactionService(runtime).preview("install", ("fixture",))
        self.assertTrue(observed.available)
        self.assertEqual(observed.installed, expected.installed)
        result = runtime.execute_read_only([HELPER, "preview", "--operation", "install", "--package", "fixture"], action_id="probe")
        self.assertEqual(result.structured_output, payload)
        self.assertLessEqual(len(result.stdout), 4000)
        self.assertNotIn("structured_output", result.to_dict())

    @patch("core.executor.action_executor.ActionExecutor._log_action")
    @patch("core.executor.action_executor.subprocess.run")
    def test_large_independent_inventory_survives_facade(self, run, _log):
        expected = snapshot()
        rows = [f"unrelated-{index}|{nevra}" for index, nevra in enumerate(expected.installed)]
        rows.extend(("fixture|fixture-0:1-1.noarch", "gpg-pubkey|gpg-pubkey-0:12345678-deadbeef.(none)"))
        payload = "\n".join(rows) + "\n"
        self.assertGreater(len(payload), 4000)
        run.return_value = subprocess.CompletedProcess([], 0, payload, "")
        observed = verify_preview(expected, SystemActionRuntime(CommandFacade()))
        self.assertEqual(observed.state, "succeeded")

    def test_rpm_apply_is_bound_to_action_center_and_operation_id(self):
        args = snapshot().apply_vector()[1:]
        self.assertEqual(classify_command(HELPER, args), "host")
        self.assertFalse(execution_allowed(HELPER, args, authority="legacy", action_id="install-application"))
        self.assertFalse(execution_allowed(HELPER, args, authority="action_center", action_id="remove-application"))
        self.assertTrue(execution_allowed(HELPER, args, authority="action_center", action_id="install-application"))

    def test_flatpak_install_apply_is_never_classified_read_only(self):
        from services.software.flatpak_maintenance import helper_command
        helper = helper_command()
        args = ["install-apply", "--installation", "user", "--remote", "flathub", "--ref", "app/org.example.App/x86_64/stable", "--snapshot-digest", "a" * 64]
        self.assertEqual(classify_command(helper, args), "host")
        self.assertFalse(execution_allowed(helper, args))
        self.assertTrue(execution_allowed(helper, args, authority="action_center", action_id="install-application"))

    def test_source_apply_requires_matching_source_action(self):
        from services.software.setup_sources import INSTALLED_HELPER
        args = ["apply", "--source-id", "rpmfusion-free", "--scope", "system", "--snapshot-digest", "a" * 64]
        self.assertFalse(execution_allowed(INSTALLED_HELPER, args))
        self.assertFalse(execution_allowed(INSTALLED_HELPER, args, authority="action_center", action_id="enable-flathub"))
        self.assertTrue(execution_allowed(INSTALLED_HELPER, args, authority="action_center", action_id="enable-rpm-fusion"))
