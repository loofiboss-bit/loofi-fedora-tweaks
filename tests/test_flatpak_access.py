"""Installation binding, independent failure states, and privacy regression tests."""
import json
import subprocess
import unittest
from unittest.mock import Mock, patch

from core.catalog_models import NativeHandoffId
from core.executor.action_result import ActionResult
from services.desktop.native_handoff import NativeHandoffService
from services.software.flatpak_access import FlatpakAccessService, parse_access
from services.software.installed_applications import InstalledApplication, InstalledInventory

REF = "app/org.example.App/x86_64/stable"


class TestFlatpakAccess(unittest.TestCase):
    def service(self, scope="user", response="[Application]\nname=org.example.App\n"):
        inventory = Mock()
        inventory.flatpaks.return_value = InstalledInventory((InstalledApplication("Example", "org.example.App", "flatpak", scope, REF),))
        probe = Mock(return_value=ActionResult.ok("read", stdout=response))
        return FlatpakAccessService(probe=probe, inventory=inventory), probe

    def test_exact_ref_and_installation_are_required(self):
        service, probe = self.service()
        self.assertEqual(service.inspect(REF, "system").status, "unavailable")
        self.assertEqual(service.inspect(REF.replace("stable", "beta"), "user").status, "unavailable")
        self.assertEqual(service.inspect("--bad", "user").status, "unavailable")
        self.assertEqual(service.inspect(REF, "--bad").status, "unavailable")
        probe.assert_not_called()

    def test_shared_layers_include_current_user(self):
        service, probe = self.service("work")
        report = service.inspect(REF, "work")
        self.assertEqual(report.status, "available")
        self.assertEqual([(layer.kind, layer.installation) for layer in report.layers],
                         [("declared", "work"), ("global-overrides", "work"), ("app-overrides", "work"),
                          ("global-overrides", "user"), ("app-overrides", "user")])
        self.assertEqual(probe.call_args_list[0].args[0], ("flatpak", "info", "--installation=work", "--show-metadata", REF))
        self.assertEqual(probe.call_args_list[-1].args[0], ("flatpak", "override", "--user", "--show", "org.example.App"))

    def test_partial_is_not_empty_or_available(self):
        service, probe = self.service()
        probe.side_effect = [ActionResult.ok("read", stdout="[Context]\nshared=network;\n"), ActionResult(False, "error"), ActionResult.ok("read")]
        report = service.inspect(REF, "user")
        self.assertEqual(report.status, "partial")
        self.assertEqual(report.layers[1].status, "unknown")
        self.assertEqual(report.layers[2].status, "available")

    def test_redaction_precedes_serialization(self):
        raw = "[Environment]\nTOKEN=secret-data\n[Context]\nfilesystems=/home/alice/Private:ro;xdg-documents/company-secret;home:ro;\nother=/private/value\nshared=network;\n"
        service, _probe = self.service(response=raw)
        payload = json.dumps(service.inspect(REF, "user").to_dict())
        for private in ("secret-data", "alice", "Private", "company-secret", "/private/value", "TOKEN"):
            self.assertNotIn(private, payload)
        self.assertIn("home:ro", payload)
        self.assertIn("Network access", payload)

    def test_malformed_and_oversize_layers_fail(self):
        for raw in ("invalid", "[Context]\nshared=a\nshared=b", "x" * 65537):
            service, _probe = self.service(response=raw)
            self.assertEqual(service.inspect(REF, "user").status, "unavailable")
        self.assertEqual(parse_access(""), ())

    def test_flatseal_requires_installed_exact_id(self):
        runner = Mock(side_effect=[subprocess.CompletedProcess([], 0, "com.github.tchx84.Flatseal.Other\n"),
                                   subprocess.CompletedProcess([], 0, "com.github.tchx84.Flatseal\n")])
        service = NativeHandoffService(which=lambda _name: "/usr/bin/flatpak", runner=runner)
        availability = service.availability(NativeHandoffId.FLATSEAL)
        self.assertTrue(availability.available)
        self.assertEqual(availability.target.arguments, ("run", "--system", "com.github.tchx84.Flatseal"))
        self.assertTrue(all(call.kwargs["timeout"] == 3 for call in runner.call_args_list))

    def test_private_keys_and_all_unknown(self):
        entries = parse_access("[Session Bus Policy]\n/home/alice/private=own\n[Context]\n/private/key=secret\n")
        payload = json.dumps([entry.__dict__ for entry in entries])
        self.assertNotIn("alice", payload)
        self.assertNotIn("/private", payload)
        service, probe = self.service()
        probe.return_value = ActionResult(False, "failed")
        self.assertEqual(service.inspect(REF, "user").status, "unavailable")

    def test_cancel_stops_probing_between_layers(self):
        inventory = Mock()
        inventory.flatpaks.return_value = InstalledInventory((InstalledApplication("Example", "org.example.App", "flatpak", "user", REF),))
        probe = Mock(return_value=ActionResult.ok("read", stdout="[Context]\nshared=network;\n"))
        cancelled = Mock(side_effect=[False, True, True])
        service = FlatpakAccessService(probe=probe, inventory=inventory, cancelled=cancelled)
        self.assertEqual(service.inspect(REF, "user").status, "partial")
        self.assertEqual(probe.call_count, 1)

    def test_missing_flatseal_is_unavailable(self):
        runner = Mock(return_value=subprocess.CompletedProcess([], 0, ""))
        service = NativeHandoffService(which=lambda _name: "/usr/bin/flatpak", runner=runner)
        self.assertIsNone(service.prepare_launch(NativeHandoffId.FLATSEAL))

    @patch("services.software.flatpak_access.FlatpakAccessService")
    @patch("cli.commands.apps_commands.detect_platform_profile")
    def test_cli_reports_same_versioned_model(self, detect, access_service):
        from types import SimpleNamespace
        from cli.commands.apps_commands import handle_apps
        service, _probe = self.service()
        report = service.inspect(REF, "user")
        access_service.return_value.inspect.return_value = report
        output = Mock()
        result = handle_apps(SimpleNamespace(apps_action="access", ref=REF, installation="user"), True, output, Mock())
        self.assertEqual(result, 0)
        self.assertEqual(output.call_args.args[0]["schema"], "loofi.flatpak-access/v1")
        access_service.return_value.inspect.assert_called_once_with(REF, "user")

    @patch("subprocess.run")
    @patch("ui.native_handoff_card.NativeHandoffCard.refresh_availability")
    def test_access_dialog_uses_captured_layers(self, refresh, runner):
        from PyQt6.QtWidgets import QApplication
        from ui.flatpak_insights import FlatpakAccessDialog
        application = QApplication.instance() or QApplication([])
        service, _probe = self.service(response="[Context]\nshared=network;\n")
        app = service.inventory.flatpaks().applications[0]
        dialog = FlatpakAccessDialog(app, service.inspect(REF, "user"))
        refresh.assert_not_called()
        runner.assert_not_called()
        self.assertIn("Understand", dialog.windowTitle())
        dialog.close()
        application.processEvents()


class TestAccessWorkerLifecycle(unittest.TestCase):
    @patch("ui.flatpak_insights.QProcess.startDetached")
    @patch("services.system.system.SystemManager.get_platform_profile")
    @patch("services.desktop.native_handoff.NativeHandoffService")
    @patch("ui.flatpak_insights.OperationControllerQtAdapter")
    def test_launch_preflight_is_deferred_and_close_suppresses_launch(self, adapter_type, native, profile, detached):
        from PyQt6.QtWidgets import QApplication
        from ui.flatpak_insights import FlatpakInsightsCard
        application = QApplication.instance() or QApplication([])
        adapter = adapter_type.return_value
        adapter.busy = False
        adapter.cancel_requested = False
        card = FlatpakInsightsCard(service=Mock())
        dialog = Mock()
        card._dialogs[card._generation] = dialog
        card._launch_access_tool(dialog, NativeHandoffId.FLATSEAL)
        native.assert_not_called()
        task = adapter.start.call_args.args[0]
        completion = task()
        native.return_value.prepare_launch.assert_called_once()
        card._access_closed(card._generation)
        adapter.cancel.assert_called_once()
        card._result(completion)
        detached.assert_not_called()
        card.cleanup(250)
        adapter.close.assert_called_once_with(250)
        card.close()
        application.processEvents()

    @patch("services.desktop.native_handoff.NativeHandoffService")
    @patch("ui.flatpak_insights.OperationControllerQtAdapter")
    def test_access_inspection_sets_generation_and_does_not_probe_on_ui_thread(self, adapter_type, native):
        from PyQt6.QtWidgets import QApplication
        from ui.flatpak_insights import FlatpakInsightsCard
        application = QApplication.instance() or QApplication([])
        adapter = adapter_type.return_value
        adapter.busy = False
        card = FlatpakInsightsCard(service=Mock())
        card.show_access(InstalledApplication("Example", "org.example.App", "flatpak", "user", REF))
        self.assertEqual(card._active_generation, card._generation)
        self.assertIn("Reading", card.status.text())
        native.assert_not_called()
        adapter.start.assert_called_once()
        self.assertFalse(card.access_stop_button.isHidden())
        card.access_stop_button.click()
        adapter.cancel.assert_called_once()
        card._stopped()
        self.assertTrue(card.access_stop_button.isHidden())
        card.cleanup()
        self.assertEqual(adapter.cancel.call_count, 2)
        adapter.close.assert_called_once_with(1000)
        card.close()
        application.processEvents()
