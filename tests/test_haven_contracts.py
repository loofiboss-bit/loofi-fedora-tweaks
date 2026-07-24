"""Focused branch coverage for Haven trust-boundary helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.execution_policy import classify_command, execution_allowed
from core.export.support_bundle import (
    CURRENT_SUPPORT_BUNDLE_VERSION,
    MIN_SUPPORT_BUNDLE_VERSION,
    import_legacy_bundle,
)
from core.plugins.legacy import LegacyExtensionService
from core.product_catalog import catalog_entry
from core.secrets import SecretStore
from daemon.plan_boundary import create_manual_plan, create_plan
from daemon.handlers.firewall_handler import FirewallHandler
from daemon.handlers.network_handler import NetworkHandler
from daemon.handlers.package_handler import PackageHandler
from daemon.handlers.service_handler import ServiceHandler


class TestExecutionClassification(unittest.TestCase):
    def test_supported_command_matrix_is_closed(self):
        cases = {
            ("flatpak-spawn", ("--host", "dnf", "install", "vim")): "host",
            ("rpm", ("-q", "vim")): "read_only",
            ("rpm", ("-i", "vim.rpm")): "host",
            ("rpm-ostree", ("upgrade", "--check")): "read_only",
            ("rpm-ostree", ("install", "vim")): "host",
            ("flatpak", ("list",)): "read_only",
            ("flatpak", ("install", "flathub", "app.id")): "host",
            ("fwupdmgr", ("get-updates",)): "read_only",
            ("fwupdmgr", ("update",)): "host",
            ("systemctl", ("status", "sshd.service")): "read_only",
            ("systemctl", ("restart", "sshd.service")): "host",
            ("journalctl", ("--vacuum-time=7d",)): "host",
            ("firewall-cmd", ("--list-all",)): "read_only",
            ("firewall-cmd", ("--add-service=ssh",)): "host",
            ("nmcli", ("connection", "up", "home")): "host",
            ("nmcli", ("connection", "show")): "read_only",
            ("timeshift", ("--list",)): "read_only",
            ("timeshift", ("--create",)): "host",
            ("snapper", ("list",)): "read_only",
            ("snapper", ("delete", "1")): "host",
            ("sysctl", ("-w", "a=b")): "host",
            ("unknown-tool", ("write",)): "manual_only",
        }
        for (command, args), expected in cases.items():
            with self.subTest(command=command, args=args):
                self.assertEqual(classify_command(command, args), expected)

        self.assertFalse(execution_allowed("systemctl", ["restart", "x.service"]))
        self.assertTrue(
            execution_allowed(
                "systemctl", ["restart", "x.service"], authority="action_center"
            )
        )


class TestSecretStoreBranches(unittest.TestCase):
    def tearDown(self):
        SecretStore._session.clear()

    def test_keyring_priority_and_read_failures_fall_back_to_session(self):
        backend = SimpleNamespace(priority=0)
        module = MagicMock(get_keyring=MagicMock(return_value=backend))
        with patch.dict("sys.modules", {"keyring": module}):
            self.assertFalse(SecretStore.persistent_available())

        keyring = MagicMock()
        keyring.get_password.side_effect = OSError("locked")
        SecretStore._session["account"] = "session"
        with patch.object(SecretStore, "_keyring", return_value=keyring):
            self.assertEqual(SecretStore.get("account"), "session")

    def test_set_readback_failure_and_write_failure_use_no_plaintext_file(self):
        keyring = MagicMock()
        keyring.get_password.return_value = "different"
        with patch.object(SecretStore, "_keyring", return_value=keyring):
            result = SecretStore.set("account", "secret")
        self.assertFalse(result.success)

        keyring.set_password.side_effect = RuntimeError("locked")
        with patch.object(SecretStore, "_keyring", return_value=keyring):
            result = SecretStore.set("account", "session-secret")
        self.assertTrue(result.success)
        self.assertFalse(result.persistent)
        self.assertEqual(SecretStore._session["account"], "session-secret")
        self.assertFalse(SecretStore.set("", "secret").success)

    def test_delete_and_migration_failure_paths(self):
        errors = SimpleNamespace(PasswordDeleteError=type("PasswordDeleteError", (Exception,), {}))
        keyring = MagicMock(errors=errors)
        keyring.delete_password.side_effect = OSError("locked")
        with patch.object(SecretStore, "_keyring", return_value=keyring):
            self.assertFalse(SecretStore.delete("account"))

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "token"
            path.write_text("", encoding="utf-8")
            result = SecretStore.migrate_plaintext("account", path)
            self.assertIsNotNone(result)
            self.assertFalse(result.success)

            path.write_text("secret", encoding="utf-8")
            persistent = SimpleNamespace(success=True, persistent=True)
            with (
                patch.object(SecretStore, "set", return_value=persistent),
                patch.object(SecretStore, "get_persistent", return_value="secret"),
                patch("core.secrets.durable_unlink", side_effect=OSError("busy")),
            ):
                result = SecretStore.migrate_plaintext("account", path)
            self.assertTrue(result.persistent)
            self.assertFalse(result.success)


class TestCatalogLegacyAndPlanHelpers(unittest.TestCase):
    def test_catalog_projection_properties_and_missing_lookup(self):
        entry = catalog_entry("community:marketplace")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.plugin_id, "community")
        self.assertTrue(entry.allowed_variants)
        self.assertIsNone(catalog_entry("missing:route"))

    def test_legacy_inventory_ignores_files_and_symlinks_and_exports(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "zeta").mkdir()
            (root / "zeta" / "plugin.json").write_text("{}", encoding="utf-8")
            (root / "plain.txt").write_text("data", encoding="utf-8")
            (root / "linked").symlink_to(root / "zeta", target_is_directory=True)
            records = LegacyExtensionService.list_extensions(root)
            self.assertEqual([record.name for record in records], ["zeta"])
            self.assertTrue(records[0].manifest_present)
            with patch("core.plugins.legacy.atomic_write_json") as writer:
                LegacyExtensionService.export_manifest(root / "export.json", root)
            self.assertEqual(writer.call_args.kwargs["mode"], 0o600)

    def test_support_bundle_legacy_adapter_is_explicit(self):
        self.assertEqual(
            import_legacy_bundle(
                {"support_bundle_version": MIN_SUPPORT_BUNDLE_VERSION}
            )["support_bundle_version"],
            MIN_SUPPORT_BUNDLE_VERSION,
        )
        self.assertEqual(
            import_legacy_bundle(
                {"support_bundle_version": CURRENT_SUPPORT_BUNDLE_VERSION}
            )["support_bundle_version"],
            CURRENT_SUPPORT_BUNDLE_VERSION,
        )
        for value in (
            None,
            MIN_SUPPORT_BUNDLE_VERSION - 1,
            CURRENT_SUPPORT_BUNDLE_VERSION + 1,
            str(CURRENT_SUPPORT_BUNDLE_VERSION),
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                import_legacy_bundle({"support_bundle_version": value})

    @patch("daemon.plan_boundary.ActionCenterOrchestrator")
    def test_daemon_helpers_only_return_unconfirmed_plans(self, orchestrator_cls):
        plan = MagicMock()
        plan.to_dict.return_value = {"plan_id": "plan-1"}
        orchestrator_cls.return_value.plan.return_value = plan
        payload = create_plan("update-flatpaks")
        self.assertTrue(payload["plan_only"])
        self.assertFalse(payload["auto_apply"])
        self.assertTrue(payload["requires_interactive_confirmation"])
        create_manual_plan("Reset Host", {"reason": "test"})
        self.assertEqual(
            orchestrator_cls.return_value.plan.call_args_list[-1].args[0],
            "daemon-reset-host",
        )


class TestDaemonMutationMatrix(unittest.TestCase):
    @patch("daemon.handlers.package_handler.create_manual_plan", return_value={"plan_only": True})
    @patch("daemon.handlers.package_handler.create_plan", return_value={"plan_only": True})
    def test_package_mutations_only_create_plans(self, bounded, manual):
        for call in (
            lambda: PackageHandler.install(["vim"]),
            lambda: PackageHandler.install(["vim", "git"]),
            lambda: PackageHandler.remove(["vim"]),
            lambda: PackageHandler.remove(["vim", "git"]),
            lambda: PackageHandler.update(),
            lambda: PackageHandler.update(["vim"]),
        ):
            self.assertTrue(call()["plan_only"])
        self.assertEqual(bounded.call_count, 3)
        self.assertEqual(manual.call_count, 3)

    @patch("daemon.handlers.firewall_handler.create_manual_plan", return_value={"plan_only": True})
    def test_firewall_mutations_only_create_manual_plans(self, create):
        calls = (
            lambda: FirewallHandler.set_default_zone("public"),
            lambda: FirewallHandler.add_service("ssh", "public", True),
            lambda: FirewallHandler.remove_service("ssh", "public", False),
            lambda: FirewallHandler.add_rich_rule('rule family="ipv4" accept', "public", True),
            lambda: FirewallHandler.remove_rich_rule('rule family="ipv4" accept', "public", True),
            lambda: FirewallHandler.open_port("8080", "tcp", "public", True),
            lambda: FirewallHandler.close_port("8080", "tcp", "public", False),
            FirewallHandler.start_firewall,
            FirewallHandler.stop_firewall,
        )
        for call in calls:
            self.assertTrue(call()["plan_only"])
        self.assertEqual(create.call_count, len(calls))

    @patch("daemon.handlers.network_handler.create_manual_plan", return_value={"plan_only": True})
    def test_network_mutations_only_create_manual_plans(self, create):
        calls = (
            lambda: NetworkHandler.reactivate_connection("home"),
            lambda: NetworkHandler.connect_wifi("Fedora WiFi"),
            lambda: NetworkHandler.disconnect_wifi("wlan0"),
            lambda: NetworkHandler.apply_dns("home", "1.1.1.1,1.0.0.1"),
            lambda: NetworkHandler.set_hostname_privacy("home", True),
        )
        for call in calls:
            self.assertTrue(call()["plan_only"])
        self.assertEqual(create.call_count, len(calls))

    @patch("daemon.handlers.service_handler.create_plan", return_value={"plan_only": True})
    @patch("daemon.handlers.service_handler.create_manual_plan", return_value={"plan_only": True})
    def test_system_service_mutations_only_create_plans(self, manual, bounded):
        calls = (
            lambda: ServiceHandler.reboot("review", 0),
            lambda: ServiceHandler.shutdown("review", 1),
            lambda: ServiceHandler.suspend("review"),
            lambda: ServiceHandler.update_grub("review"),
            lambda: ServiceHandler.set_hostname("fedora-test", "review"),
            lambda: ServiceHandler.start_unit("demo.service", "user"),
            lambda: ServiceHandler.stop_unit("demo.service", "user"),
            lambda: ServiceHandler.restart_unit("demo.service", "user"),
            lambda: ServiceHandler.restart_unit("demo.service", "system"),
            lambda: ServiceHandler.mask_unit("demo.service", "user"),
            lambda: ServiceHandler.unmask_unit("demo.service", "user"),
        )
        for call in calls:
            self.assertTrue(call()["plan_only"])
        self.assertEqual(bounded.call_count, 1)
        self.assertEqual(manual.call_count, len(calls) - 1)


if __name__ == "__main__":
    unittest.main()
