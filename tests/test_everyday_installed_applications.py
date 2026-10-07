"""Exact installation inventory and fail-closed removal regressions."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.actions.installed_applications import installed_application_definitions
from core.executor.action_result import ActionResult
from core.tasks.applications import ApplicationCatalog, ApplicationContext
from core.catalog_models import FedoraVariant
from services.software.installed_applications import InstalledApplicationService, parse_flatpak_inventory

ROW = "Firefox\torg.mozilla.firefox\tapp/org.mozilla.firefox/x86_64/stable\t1\t20 MB\tuser\n"


class InstalledApplicationTests(unittest.TestCase):
    def test_flatpak_list_short_ref_is_normalized(self):
        apps = parse_flatpak_inventory(ROW.replace("app/org.mozilla", "org.mozilla"))
        self.assertEqual(apps[0].ref, "app/org.mozilla.firefox/x86_64/stable")

    def test_duplicate_app_scopes_are_distinct(self):
        apps = parse_flatpak_inventory(ROW + ROW.replace("\tuser\n", "\tsystem\n") + ROW.replace("\tuser\n", "\twork\n"))
        self.assertEqual([app.installation for app in apps], ["user", "system", "work"])

    def test_malformed_inventory_cannot_mean_absence(self):
        service = InstalledApplicationService(probe=Mock(return_value=ActionResult(True, "ok", stdout="bad")))
        result = service.flatpaks()
        self.assertTrue(result.errors)
        self.assertIn("flatpak", result.unknown_sources)

    def test_partial_inventory_keeps_successful_source(self):
        probe = Mock(side_effect=[ActionResult(True, "ok", stdout=ROW), ActionResult(False, "rpm missing")])
        result = InstalledApplicationService(probe=probe).snapshot()
        self.assertEqual(len(result.applications), 1)
        self.assertEqual(result.unknown_sources, frozenset({"fedora"}))

    def test_unknown_source_not_available_to_install(self):
        context = ApplicationContext(variant=FedoraVariant.TRADITIONAL, unknown_sources=frozenset({"flatpak"}))
        self.assertFalse(ApplicationCatalog().eligibility("firefox", context).selectable)

    def test_missing_tools_explicit(self):
        result = InstalledApplicationService(probe=Mock(return_value=ActionResult(False, "missing"))).snapshot()
        self.assertEqual(result.unknown_sources, frozenset({"flatpak", "fedora"}))

    def test_executor_rejects_unscoped_or_data_deleting_removal(self):
        from core.executor.command_policy import CommandValidationError, validate_command
        ref = "app/org.mozilla.firefox/x86_64/stable"
        valid = ["uninstall", "--user", "--assumeyes", "--noninteractive", "--no-related", ref]
        validate_command("flatpak", valid)
        for invalid in (valid[:1] + valid[2:], valid + ["--delete-data"],
                        [*valid[:-1], "org.mozilla.firefox"], [valid[0], "--installation=../bad", *valid[2:]]):
            with self.subTest(args=invalid), self.assertRaises(CommandValidationError):
                validate_command("flatpak", invalid)

    def test_exact_removal_and_data_preservation(self):
        definition = installed_application_definitions()[0]
        parameters = {"ref": "app/org.mozilla.firefox/x86_64/stable", "installation": "work"}
        vector = definition.command_renderer(parameters, Mock())
        self.assertIn("--installation=work", vector)
        self.assertIn("--no-related", vector)
        self.assertNotIn("--delete-data", vector)
        self.assertNotIn("--force-remove", vector)
        self.assertEqual(vector[-1], parameters["ref"])

    def test_running_app_blocks_removal_across_scopes(self):
        runtime = Mock()
        runtime.execute_read_only.side_effect = [ActionResult(True, "ok", stdout=ROW), ActionResult(True, "ok", stdout="org.mozilla.firefox\n")]
        definition = installed_application_definitions()[0]
        result = definition.preflight_checker({"ref": "app/org.mozilla.firefox/x86_64/stable", "installation": "user"}, runtime)
        self.assertEqual(result.reason_code, "application_running")

    def test_running_probe_failure_blocks_removal(self):
        runtime = Mock()
        runtime.execute_read_only.side_effect = [ActionResult(True, "ok", stdout=ROW), ActionResult(False, "unreadable")]
        result = installed_application_definitions()[0].preflight_checker({"ref": "app/org.mozilla.firefox/x86_64/stable", "installation": "user"}, runtime)
        self.assertFalse(result.allowed)
        self.assertEqual(result.reason_code, "running_state_unknown")

    def test_verification_read_failure_is_not_success(self):
        runtime = Mock()
        runtime.execute_read_only.return_value = ActionResult(False, "unreadable")
        plan = SimpleNamespace(parameters={"ref": "app/org.mozilla.firefox/x86_64/stable", "installation": "user"})
        self.assertEqual(installed_application_definitions()[0].verifier(Mock(), plan, runtime).state, "failed")

    def test_verification_ignores_other_installations(self):
        runtime = Mock()
        runtime.execute_read_only.return_value = ActionResult(True, "ok", stdout=ROW.replace("\tuser\n", "\tsystem\n"))
        plan = SimpleNamespace(parameters={"ref": "app/org.mozilla.firefox/x86_64/stable", "installation": "user"})
        self.assertEqual(installed_application_definitions()[0].verifier(Mock(), plan, runtime).state, "succeeded")

    def test_real_controller_lifecycle_verifies_exact_removal(self):
        import tempfile
        from pathlib import Path
        from core.actions import ActionCatalog, ActionCenterOrchestrator, ActionPlanStore, ActionRunStore
        from core.actions.operation_controller import OperationController
        present = [True]

        def probe(vector, **_kwargs):
            output = ROW if vector[1] == "list" and present[0] else ""
            return ActionResult(True, "read", exit_code=0, stdout=output)

        def execute(_command, **_kwargs):
            present[0] = False
            return ActionResult(True, "removed", exit_code=0)

        runtime = SimpleNamespace(is_atomic=lambda: False, package_manager=lambda: "dnf5",
                                  fedora_version=lambda: "44", boot_id=lambda: "boot-a",
                                  package_manager_busy=lambda: False, execute_read_only=probe)
        facade = Mock()
        facade.execute.side_effect = execute
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        orchestrator = ActionCenterOrchestrator(
            facade=facade, catalog=ActionCatalog(installed_application_definitions()), runtime=runtime,
            plan_store=ActionPlanStore(root / "plans.json"), run_store=ActionRunStore(root / "runs.jsonl"), lease_path=root / "lease",
        )
        controller = OperationController(orchestrator=orchestrator, facade=facade)
        ticket = controller.prepare("remove-installed-flatpak", {"ref": "app/org.mozilla.firefox/x86_64/stable", "installation": "user"})
        self.assertTrue(ticket.plan.policy_decision.allowed)
        confirmed = controller.confirm(ticket, confirmed=True, accept_no_rollback=True)
        self.assertEqual(confirmed.status, "prepared")
        executed = controller.run(confirmed)
        self.assertEqual(executed.status, "verifying")
        verified = controller.verify(executed)
        self.assertEqual(verified.status, "succeeded")
        facade.execute.assert_called_once()
        with self.subTest("desktop authorization denied"):
            present[0] = True
            facade.execute.side_effect = lambda *_args, **_kwargs: ActionResult.fail("Authorization denied", exit_code=1)
            ticket = controller.prepare("remove-installed-flatpak", {"ref": "app/org.mozilla.firefox/x86_64/stable", "installation": "user"})
            denied = controller.run(controller.confirm(ticket, confirmed=True, accept_no_rollback=True))
            self.assertEqual(denied.status, "failed")
            self.assertTrue(present[0])
            self.assertFalse(denied.success)

    def test_reject_command_injection_and_runtime_refs(self):
        definition = installed_application_definitions()[0]
        for ref, scope in [("app/id/arch/branch", "--system"), ("runtime/org.test.App/x86_64/stable", "user"), ("app/org.test.App/x86_64/stable;rm", "user")]:
            self.assertFalse(definition.parameter_validator({"ref": ref, "installation": scope}).allowed)

    @patch("services.software.flatpak.subprocess.run")
    @patch("services.software.flatpak.FlatpakManager.is_available", return_value=True)
    def test_permissions_are_bound_to_exact_scope(self, _available, run):
        from services.software.flatpak import FlatpakManager
        run.return_value = SimpleNamespace(returncode=0, stdout="")
        FlatpakManager.get_flatpak_permissions("app/org.mozilla.firefox/x86_64/stable", installation="work", strict=True)
        self.assertEqual(run.call_args_list[0].args[0], ["flatpak", "info", "--installation=work", "--show-permissions", "app/org.mozilla.firefox/x86_64/stable"])


class InstalledApplicationsPresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_inventory_updates_catalog_and_exact_removal_review(self):
        from PyQt6.QtWidgets import QPushButton
        from ui.install_workflow import InstallWorkflowPage
        from services.software.installed_applications import InstalledInventory
        page = InstallWorkflowPage(context=ApplicationContext(variant=FedoraVariant.TRADITIONAL))
        received = []
        page.actionReviewRequested.connect(lambda action, parameters: received.append((action, parameters)))
        page.installed_card.apply_inventory(InstalledInventory(parse_flatpak_inventory(ROW)))
        self.assertEqual(page.catalog.eligibility("firefox", page.context).state, "installed")
        button = next(button for button in page.installed_card.findChildren(QPushButton) if button.text() == "Review removal")
        button.click()
        self.assertEqual(received, [("remove-installed-flatpak", {"ref": "app/org.mozilla.firefox/x86_64/stable", "installation": "user"})])
        page.view_filter.setCurrentIndex(1)
        self.assertTrue(page.application_list.isHidden())
        self.assertFalse(page.installed_card.isHidden())
        self.assertTrue(page.flathub_status_card.isHidden())
        page.deleteLater()

    def test_installed_search_filters_preserved_installation_identities(self):
        from ui.install_workflow import InstallWorkflowPage
        from services.software.installed_applications import InstalledInventory

        inventory = InstalledInventory(parse_flatpak_inventory(
            ROW + ROW.replace("\tuser\n", "\tsystem\n")
        ))
        page = InstallWorkflowPage(context=ApplicationContext(variant=FedoraVariant.TRADITIONAL))
        page.installed_card.apply_inventory(inventory)
        page.view_filter.setCurrentIndex(page.view_filter.findData("installed"))
        page.search_input.setText("system")

        visible = [app.installation for app, row in page.installed_card._application_rows if not row.isHidden()]

        self.assertEqual(visible, ["system"])
        self.assertIn("Showing 1 of 2", page.installed_card.search_summary.text())
        self.assertEqual(page.installed_card.inventory, inventory)
        page.deleteLater()

    def test_permission_dialog_groups_known_grants_and_hides_environment_values(self):
        from types import SimpleNamespace
        from PyQt6.QtWidgets import QPlainTextEdit
        from ui.installed_applications import FlatpakPermissionsDialog
        from services.software.flatpak import FlatpakPermission

        app = parse_flatpak_inventory(ROW)[0]
        permissions = SimpleNamespace(permissions=[
            FlatpakPermission("Context", "shared", "network"),
            FlatpakPermission("Context", "filesystems", "home:ro"),
            FlatpakPermission("Context", "filesystems", "!host"),
            FlatpakPermission("Environment", "API_TOKEN", "secret-value"),
            FlatpakPermission("Unknown section", "odd-key", "odd-value"),
        ])
        dialog = FlatpakPermissionsDialog(app, permissions)
        rendered = dialog.findChild(QPlainTextEdit).toPlainText()
        self.assertIn("Network", rendered)
        self.assertIn("Files", rendered)
        self.assertIn("read-only", rendered)
        self.assertIn("Access denied", rendered)
        self.assertIn("Technical details", rendered)
        self.assertIn("Unknown section / odd-key: odd-value", rendered)
        self.assertIn("Value hidden for privacy", rendered)
        self.assertNotIn("secret-value", rendered)
        dialog.close()

    def test_permission_dialog_stays_readable_with_large_text_and_theme_palettes(self):
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QColor, QFont, QPalette
        from PyQt6.QtTest import QTest
        from PyQt6.QtWidgets import QDialogButtonBox, QPlainTextEdit
        from ui.installed_applications import FlatpakPermissionsDialog
        from services.software.flatpak import FlatpakPermission
        from types import SimpleNamespace

        app = parse_flatpak_inventory(ROW)[0]
        permissions = SimpleNamespace(permissions=[FlatpakPermission("Context", "shared", "network")])
        original_palette = self.app.palette()
        try:
            for base, text in (("#ffffff", "#111111"), ("#202124", "#f1f3f4")):
                palette = QPalette(original_palette)
                palette.setColor(QPalette.ColorRole.Base, QColor(base))
                palette.setColor(QPalette.ColorRole.Text, QColor(text))
                palette.setColor(QPalette.ColorRole.Window, QColor(base))
                palette.setColor(QPalette.ColorRole.WindowText, QColor(text))
                self.app.setPalette(palette)
                dialog = FlatpakPermissionsDialog(app, permissions)
                font = QFont(dialog.font())
                font.setPointSize(20)
                dialog.setFont(font)
                dialog.resize(420, 320)
                dialog.show()
                self.app.processEvents()
                details = dialog.findChild(QPlainTextEdit)
                self.assertTrue(details.isReadOnly())
                self.assertGreater(details.height(), 0)
                self.assertEqual(details.palette().color(QPalette.ColorRole.Base).name(), base)
                close = dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Close)
                close.setFocus()
                QTest.keyClick(close, Qt.Key.Key_Return)
                self.app.processEvents()
                self.assertFalse(dialog.isVisible())
                dialog.deleteLater()
        finally:
            self.app.setPalette(original_palette)

    def test_profile_selection_dialog_supports_keyboard_and_large_text(self):
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QFont
        from PyQt6.QtTest import QTest
        from ui.tweak_profiles import ProfileSelectionDialog

        dialog = ProfileSelectionDialog(
            "Review preset",
            "Select the available changes. Unsupported settings remain visible with a reason.",
            [("gnome-animations", "Animations: true → false [ready]", True),
             ("missing-setting", "Missing setting: schema unavailable [unavailable]", False)],
        )
        font = QFont(dialog.font())
        font.setPointSize(20)
        dialog.setFont(font)
        dialog.resize(420, 320)
        dialog.show()
        self.app.processEvents()
        dialog.entries.setFocus()
        dialog.entries.setCurrentRow(0)
        QTest.keyClick(dialog.entries, Qt.Key.Key_Space)
        self.assertEqual(dialog.selected_ids(), ())
        QTest.keyClick(dialog, Qt.Key.Key_Escape)
        self.assertFalse(dialog.isVisible())
        dialog.deleteLater()

    def test_late_permissions_for_a_previous_selection_are_ignored(self):
        from types import SimpleNamespace
        from services.software.installed_applications import InstalledApplicationService
        from services.software.flatpak import FlatpakAppPermissions
        from ui.installed_applications import InstalledApplicationsCard

        card = InstalledApplicationsCard(service=InstalledApplicationService(probe=Mock()))
        old_app = parse_flatpak_inventory(ROW)[0]
        card._active_permission_request = (old_app, 1)
        card._permission_generation = 2
        card._permissions_result(FlatpakAppPermissions(old_app.app_id, old_app.name, []))
        self.assertEqual(card._permission_dialogs, {})
        card.cleanup()
        card.close()

    def test_selecting_another_app_closes_the_old_permission_dialog(self):
        from types import SimpleNamespace
        from ui.installed_applications import FlatpakPermissionsDialog, InstalledApplicationsCard

        app = parse_flatpak_inventory(ROW)[0]
        other = parse_flatpak_inventory(ROW.replace("x86_64", "aarch64"))[0]
        card = InstalledApplicationsCard(service=Mock())
        adapter = Mock(busy=False)
        adapter.start.return_value = True
        card._permissions_adapter = adapter
        dialog = FlatpakPermissionsDialog(app, SimpleNamespace(permissions=[]), card)
        dialog.open()
        card._permission_generation = 1
        card._permission_dialogs[1] = dialog

        card.show_permissions(other)

        self.assertFalse(dialog.isVisible())
        self.assertEqual(card._active_permission_request, (other, 2))
        adapter.start.assert_called_once()
        card.request_stop()
        card.close()
        card.deleteLater()

    def test_inventory_identity_text_stays_readable_when_scaled(self):
        from PyQt6.QtGui import QFont
        from ui.installed_applications import InstalledApplicationsCard
        from services.software.installed_applications import InstalledInventory
        card = InstalledApplicationsCard()
        font = QFont(card.font())
        font.setPointSize(20)
        card.setFont(font)
        card.apply_inventory(InstalledInventory(parse_flatpak_inventory(ROW + ROW.replace("\tuser\n", "\tsystem\n"))))
        card.resize(420, 200)
        card.show()
        for _ in range(8):
            self.app.processEvents()
        for row in card._rows:
            for label in (row.title_label, row.description_label):
                self.assertGreaterEqual(label.height(), label.heightForWidth(label.width()))
        card.close()
        card.deleteLater()

    def test_busy_cleanup_keeps_workers_owned_until_stopped(self):
        from ui.install_workflow import InstallWorkflowPage
        page = InstallWorkflowPage()
        inventory = Mock(busy=True)
        inventory.close.return_value = False
        permissions = Mock(busy=True)
        permissions.close.return_value = False
        source = Mock(busy=True)
        source.close.return_value = False
        page.installed_card._adapter = inventory
        page.installed_card._permissions_adapter = permissions
        page._source_status_adapter = source
        self.assertTrue(page.busy)
        self.assertFalse(page.cleanup(10))
        self.assertIs(page.installed_card._adapter, inventory)
        self.assertIs(page.installed_card._permissions_adapter, permissions)
        self.assertIs(page._source_status_adapter, source)
        source.cancel.assert_called()
        inventory.close.assert_called_once_with(10)
        permissions.close.assert_called_once_with(10)
        source.close.assert_called_once_with(10)
        page.deleteLater()

    @patch("ui.native_handoff_card.NativeHandoffCard.refresh_availability")
    def test_rpm_removal_uses_fixed_native_handoff_card(self, refresh):
        from core.catalog_models import NativeHandoffId
        from ui.installed_applications import InstalledApplicationsCard
        card = InstalledApplicationsCard()
        card.software_handoff.open_button.setEnabled(False)
        card.open_software_manager()
        self.assertEqual(card.software_handoff.handoff_id, NativeHandoffId.SOFTWARE_CENTER)
        refresh.assert_called_once()
        self.assertFalse(card.software_handoff.isHidden())
        card.deleteLater()

    def test_parser_removal_requires_explicit_installation(self):
        import argparse
        from cli.parser_domains.apps import register_apps_command
        parser = argparse.ArgumentParser()
        register_apps_command(parser.add_subparsers())
        with self.assertRaises(SystemExit):
            parser.parse_args(["apps", "remove", "app/org.test.App/x86_64/stable"])
        args = parser.parse_args(["apps", "remove", "app/org.test.App/x86_64/stable", "--installation", "work"])
        self.assertEqual(args.installation, "work")

    @patch("cli.commands.apps_commands.detect_platform_profile")
    @patch("cli.commands.apps_commands.TaskContext.from_platform_profile")
    @patch("cli.commands.apps_commands.OperationController")
    def test_cli_remove_confirms_then_runs_only_once(self, controller, task_context, _profile):
        from cli.commands.apps_commands import handle_apps
        from core.tasks.catalog import TaskContext
        task_context.return_value = TaskContext(variant=FedoraVariant.TRADITIONAL)
        instance = controller.return_value
        instance.prepare.return_value.plan.policy_decision.allowed = True
        instance.confirm.return_value.status = "prepared"
        instance.run.return_value.status = "verifying"
        instance.verify.return_value.status = "succeeded"
        args = SimpleNamespace(apps_action="remove", ref="app/org.test.App/x86_64/stable", installation="user", yes=True)
        self.assertEqual(handle_apps(args, False, Mock(), Mock()), 0)
        instance.confirm.assert_called_once_with(instance.prepare.return_value, confirmed=True, accept_no_rollback=True)
        instance.run.assert_called_once_with(instance.confirm.return_value)
        instance.verify.assert_called_once_with(instance.run.return_value)

    @patch("cli.commands.apps_commands.detect_platform_profile")
    @patch("cli.commands.apps_commands.TaskContext.from_platform_profile")
    @patch("cli.commands.apps_commands.OperationController")
    def test_cli_remove_denied_never_runs(self, controller, task_context, _profile):
        from cli.commands.apps_commands import handle_apps
        from core.tasks.catalog import TaskContext
        task_context.return_value = TaskContext(variant=FedoraVariant.TRADITIONAL)
        instance = controller.return_value
        instance.prepare.return_value.plan.policy_decision.allowed = False
        args = SimpleNamespace(apps_action="remove", ref="app/org.test.App/x86_64/stable", installation="system", yes=True)
        self.assertEqual(handle_apps(args, False, Mock(), Mock()), 1)
        instance.confirm.assert_not_called()
        instance.run.assert_not_called()

    @patch("cli.commands.apps_commands.detect_platform_profile")
    @patch("cli.commands.apps_commands.TaskContext.from_platform_profile")
    @patch("cli.commands.apps_commands.InstalledApplicationService")
    def test_cli_permissions_are_scoped_and_json_redacts_environment_values(self, service_class, task_context, platform):
        from cli.commands.apps_commands import handle_apps
        from services.software.flatpak import FlatpakAppPermissions, FlatpakPermission
        from services.software.installed_applications import InstalledInventory, parse_flatpak_inventory
        from core.tasks.catalog import TaskContext

        platform.return_value = object()
        task_context.return_value = TaskContext(variant=FedoraVariant.TRADITIONAL)
        app = parse_flatpak_inventory(ROW)[0]
        service = service_class.return_value
        service.flatpaks.return_value = InstalledInventory((app,))
        service.permissions.return_value = FlatpakAppPermissions(
            app.app_id, app.name,
            [FlatpakPermission("Environment", "API_TOKEN", "secret-value")],
            app.ref, app.installation,
        )
        payloads = []
        args = SimpleNamespace(apps_action="permissions", ref=app.ref, installation=app.installation)
        self.assertEqual(handle_apps(args, True, payloads.append, Mock()), 0)
        service.permissions.assert_called_once_with(app)
        self.assertEqual(payloads[0]["installation"], "user")
        self.assertEqual(payloads[0]["permissions"][0]["value"], "[hidden]")
        self.assertNotIn("secret-value", str(payloads))

        args.ref = "app/org.mozilla.firefox/aarch64/stable"
        errors = []
        self.assertEqual(handle_apps(args, True, errors.append, Mock()), 1)
        self.assertEqual(service.permissions.call_count, 1)
        self.assertEqual(errors[0]["schema"], "loofi.flatpak-permissions/v1")
        self.assertEqual(errors[0]["status"], "unavailable")
        self.assertEqual(errors[0]["permissions"], [])
