"""Care application projections, scoped metadata and runtime review regressions."""
import argparse
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.catalog_models import FedoraVariant
from services.software.installed_applications import InstalledApplication, InstalledInventory, filter_installed_applications


class CareProjectionTests(unittest.TestCase):
    def test_combined_filters_and_sort_preserve_exact_identity(self):
        small = InstalledApplication("Editor", "org.test.Editor", "flatpak", "work", "app/org.test.Editor/x86_64/stable", size="1 MB")
        large = InstalledApplication("Editor", "org.test.Editor", "flatpak", "user", small.ref, size="2 GiB")
        unknown = InstalledApplication("Other", "org.test.Other", "flatpak", "user", "app/org.test.Other/x86_64/stable", size="?")
        rpm = InstalledApplication("Editor", "editor", "fedora", "system", "editor", size="100 B")
        inventory = InstalledInventory((small, unknown, rpm, large))
        self.assertEqual(filter_installed_applications(inventory, source="flatpak", sort="size"), (large, small, unknown))
        self.assertEqual(filter_installed_applications(inventory, query="editor", installation="work", source="flatpak"), (small,))
        self.assertEqual(inventory.applications, (small, unknown, rpm, large))

    def test_size_units_and_unknown_do_not_guess(self):
        self.assertEqual(InstalledApplication("a", "a", "flatpak", "user", "ref", size="1,5 MB").size_bytes, 1500000)
        self.assertIsNone(InstalledApplication("a", "a", "flatpak", "user", "ref", size="unavailable").size_bytes)

    def test_cleanup_parser_requires_refs_and_scope(self):
        from cli.parser_domains.apps import register_apps_command
        parser = argparse.ArgumentParser()
        register_apps_command(parser.add_subparsers())
        args = parser.parse_args(["apps", "cleanup", "--installation", "work", "--ref", "runtime/org.test.R/x86_64/1", "--ref", "runtime/org.test.R/x86_64/2", "--json"])
        self.assertEqual(len(args.refs), 2)
        self.assertEqual(args.installation, "work")
        with self.assertRaises(SystemExit):
            parser.parse_args(["apps", "unused"])


class CarePresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_cleanup_review_emits_exact_selected_snapshot_without_execution(self):
        from PyQt6.QtCore import Qt
        from ui.flatpak_insights import FlatpakInsightsCard
        card = FlatpakInsightsCard(service=Mock())
        metadata = SimpleNamespace(available=True, error="", installation="work", digest="review-digest", warning="", refs=(
            SimpleNamespace(ref="runtime/org.test.R/x86_64/1", size_bytes=100),
            SimpleNamespace(ref="runtime/org.test.R/x86_64/2", size_bytes=None),
        ))
        received = []
        card.actionReviewRequested.connect(lambda action, parameters: received.append((action, parameters)))
        card._result(("unused", 0, None, metadata))
        card.entries.item(1).setCheckState(Qt.CheckState.Checked)
        card.review_button.click()
        self.assertEqual(received, [("remove-unused-flatpaks", {"installation": "work", "refs": ["runtime/org.test.R/x86_64/2"], "snapshot_digest": "review-digest"})])
        self.assertIn("other users' private", card.status.text())
        card.invalidate()
        card.review()
        self.assertEqual(len(received), 1)
        card.cleanup()
        card.deleteLater()

    def test_details_display_local_eol_missing_runtime_and_exact_scope(self):
        from PyQt6.QtWidgets import QPlainTextEdit
        from services.software.flatpak_maintenance import FlatpakDetails
        from ui.flatpak_insights import AppDetailsDialog
        app = InstalledApplication("Editor", "org.test.Editor", "flatpak", "work", "app/org.test.Editor/x86_64/stable")
        details = FlatpakDetails(app.ref, "work", available=True, name=app.name, origin="private",
                                runtime="org.test.Runtime/x86_64/1", eol="This branch has ended",
                                eol_rebase="app/org.test.Editor/x86_64/new", runtime_missing=True)
        dialog = AppDetailsDialog(app, details)
        rendered = dialog.findChild(QPlainTextEdit).toPlainText()
        self.assertIn("Installation: work", rendered)
        self.assertIn("This branch has ended", rendered)
        self.assertIn("continued support is not guaranteed", rendered)
        self.assertIn("declared runtime is missing", rendered)
        self.assertIn("Reported size: Unknown", rendered)
        dialog.close()
        dialog.deleteLater()

    def test_late_details_and_shutdown_never_open_a_dialog(self):
        from ui.flatpak_insights import FlatpakInsightsCard
        card = FlatpakInsightsCard(service=Mock())
        card._generation = 2
        card._result(("details", 1, object(), SimpleNamespace(available=True)))
        self.assertEqual(card._dialogs, {})
        card.request_stop()
        card._result(("details", 2, object(), SimpleNamespace(available=True)))
        self.assertEqual(card._dialogs, {})
        card.cleanup()
        card.deleteLater()

    def test_unavailable_support_is_displayed_and_cleanup_disabled(self):
        from ui.flatpak_insights import FlatpakInsightsCard
        card = FlatpakInsightsCard(service=Mock())
        card._result(("unused", 0, None, SimpleNamespace(available=False, error="Optional libflatpak support is unavailable.")))
        self.assertIn("unavailable", card.status.text())
        self.assertFalse(card.review_button.isEnabled())
        card.cleanup()
        card.deleteLater()

    def test_details_supersede_pending_permissions(self):
        from ui.installed_applications import InstalledApplicationsCard
        card = InstalledApplicationsCard(service=Mock())
        app = InstalledApplication("Editor", "org.test.Editor", "flatpak", "work", "app/org.test.Editor/x86_64/stable")
        card._pending_permission_request = (app, 0)
        card.insights.show_details = Mock()
        card.show_details(app)
        self.assertEqual(card._permission_generation, 1)
        self.assertIsNone(card._pending_permission_request)
        card.insights.show_details.assert_called_once_with(app)
        card.cleanup()
        card.deleteLater()

    def test_filters_are_local_without_new_service_calls(self):
        from ui.installed_applications import InstalledApplicationsCard
        service = Mock()
        card = InstalledApplicationsCard(service=service)
        small = InstalledApplication("Editor", "org.test.Editor", "flatpak", "work", "app/org.test.Editor/x86_64/stable", size="1 MB")
        unknown = InstalledApplication("Other", "org.test.Other", "flatpak", "user", "app/org.test.Other/x86_64/stable")
        card.apply_inventory(InstalledInventory((small, unknown)))
        card.installation_filter.setCurrentIndex(card.installation_filter.findData("work"))
        card.set_search("Editor")
        card.sort_order.setCurrentIndex(card.sort_order.findData("size"))
        self.assertEqual([app for app, row in card._application_rows if not row.isHidden()], [small])
        service.assert_not_called()
        self.assertEqual(service.method_calls, [])
        card.cleanup()
        card.deleteLater()


class CareCliTests(unittest.TestCase):
    @patch("cli.commands.apps_commands.detect_platform_profile")
    @patch("cli.commands.apps_commands.TaskContext.from_platform_profile")
    @patch("cli.commands.apps_commands.OperationController")
    @patch("services.software.flatpak_maintenance.FlatpakMaintenanceService")
    def test_cleanup_dry_run_never_confirms_or_executes(self, service_class, controller, context, _profile):
        from cli.commands.apps_commands import handle_apps
        from core.tasks.catalog import TaskContext
        context.return_value = TaskContext(variant=FedoraVariant.TRADITIONAL)
        service_class.return_value.unused.return_value = SimpleNamespace(available=True, digest="review-digest")
        controller.return_value.prepare.return_value.plan.policy_decision.allowed = True
        args = SimpleNamespace(apps_action="cleanup", installation="work", refs=["runtime/org.test.R/x86_64/1"], yes=True)
        self.assertEqual(handle_apps(args, True, Mock(), Mock(), dry_run=True), 0)
        controller.return_value.prepare.assert_called_once_with("remove-unused-flatpaks", {
            "installation": "work", "refs": args.refs, "snapshot_digest": "review-digest",
        })
        controller.return_value.confirm.assert_not_called()
        controller.return_value.run.assert_not_called()

    @patch("cli.commands.apps_commands.detect_platform_profile")
    @patch("cli.commands.apps_commands.TaskContext.from_platform_profile")
    @patch("cli.commands.apps_commands.OperationController")
    @patch("services.software.flatpak_maintenance.FlatpakMaintenanceService")
    def test_cleanup_confirms_executes_and_verifies(self, service_class, controller, context, _profile):
        from cli.commands.apps_commands import handle_apps
        from core.tasks.catalog import TaskContext
        context.return_value = TaskContext(variant=FedoraVariant.TRADITIONAL)
        service_class.return_value.unused.return_value = SimpleNamespace(available=True, digest="digest")
        instance = controller.return_value
        instance.prepare.return_value.plan.policy_decision.allowed = True
        instance.confirm.return_value.status = "prepared"
        instance.run.return_value.status = "verifying"
        instance.verify.return_value.status = "succeeded"
        args = SimpleNamespace(apps_action="cleanup", installation="user", refs=["runtime/org.test.R/x86_64/1"], yes=True)
        self.assertEqual(handle_apps(args, True, Mock(), Mock()), 0)
        instance.confirm.assert_called_once_with(instance.prepare.return_value, confirmed=True, accept_no_rollback=True)
        instance.run.assert_called_once()
        instance.verify.assert_called_once()

    @patch("cli.commands.apps_commands.detect_platform_profile")
    @patch("cli.commands.apps_commands.TaskContext.from_platform_profile")
    @patch("services.software.flatpak_maintenance.FlatpakMaintenanceService")
    def test_details_uses_exact_scope_and_unavailable_is_failure(self, service_class, context, _profile):
        from cli.commands.apps_commands import handle_apps
        from core.tasks.catalog import TaskContext
        from services.software.flatpak_maintenance import FlatpakDetails
        context.return_value = TaskContext(variant=FedoraVariant.TRADITIONAL)
        ref = "app/org.test.Editor/x86_64/stable"
        service_class.return_value.details.return_value = FlatpakDetails(ref, "work", error="Optional support unavailable.")
        payloads = []
        args = SimpleNamespace(apps_action="details", installation="work", ref=ref)
        self.assertEqual(handle_apps(args, True, payloads.append, Mock()), 1)
        service_class.return_value.details.assert_called_once_with(ref, "work")
        self.assertFalse(payloads[0]["available"])
        self.assertEqual(payloads[0]["installation"], "work")

    @patch("cli.commands.apps_commands.detect_platform_profile")
    @patch("cli.commands.apps_commands.TaskContext.from_platform_profile")
    @patch("cli.commands.apps_commands.OperationController")
    @patch("services.software.flatpak_maintenance.FlatpakMaintenanceService")
    def test_declined_cleanup_review_returns_only_json(self, service_class, controller, context, _profile):
        from cli.commands.apps_commands import handle_apps
        from core.tasks.catalog import TaskContext
        context.return_value = TaskContext(variant=FedoraVariant.TRADITIONAL)
        service_class.return_value.unused.return_value = SimpleNamespace(available=True, digest="digest")
        instance = controller.return_value
        instance.prepare.return_value.plan.policy_decision.allowed = True
        instance.confirm.return_value.status = "blocked"
        instance.confirm.return_value.to_dict.return_value = {"status": "blocked", "message": "Review changed."}
        payloads, printer = [], Mock()
        args = SimpleNamespace(apps_action="cleanup", installation="user", refs=["runtime/org.test.R/x86_64/1"], yes=True)
        self.assertEqual(handle_apps(args, True, payloads.append, printer), 1)
        self.assertEqual(payloads, [{"status": "blocked", "message": "Review changed."}])
        printer.assert_not_called()
        instance.run.assert_not_called()

    @patch("cli.commands.apps_commands.detect_platform_profile")
    @patch("cli.commands.apps_commands.TaskContext.from_platform_profile")
    @patch("cli.commands.apps_commands.OperationController")
    @patch("services.software.flatpak_maintenance.FlatpakMaintenanceService")
    def test_invalid_metadata_inputs_return_json_without_inspection(self, service_class, controller, context, _profile):
        from cli.commands.apps_commands import handle_apps
        from core.tasks.catalog import TaskContext
        context.return_value = TaskContext(variant=FedoraVariant.TRADITIONAL)
        for args in (SimpleNamespace(apps_action="details", installation="user", ref="invalid"),
                     SimpleNamespace(apps_action="unused", installation="--system"),
                     SimpleNamespace(apps_action="cleanup", installation="user", refs=[], yes=True),
                     SimpleNamespace(apps_action="cleanup", installation="user", refs=["app/org.test.R/x86_64/1"], yes=True)):
            with self.subTest(action=args.apps_action):
                payloads, printer = [], Mock()
                self.assertEqual(handle_apps(args, True, payloads.append, printer), 1)
                self.assertEqual(len(payloads), 1)
                self.assertFalse(payloads[0]["available"])
                printer.assert_not_called()
        service_class.assert_not_called()
        controller.assert_not_called()

    def test_cleanup_help_explains_no_rollback_acceptance(self):
        from cli.parser_domains.apps import register_apps_command
        from io import StringIO
        import contextlib
        parser = argparse.ArgumentParser()
        register_apps_command(parser.add_subparsers())
        output = StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            parser.parse_args(["apps", "cleanup", "--help"])
        rendered = " ".join(output.getvalue().split())
        self.assertIn("accept manual reinstallation without rollback", rendered)

    @patch("cli.commands.apps_commands.detect_platform_profile")
    @patch("cli.commands.apps_commands.TaskContext.from_platform_profile")
    @patch("cli.commands.apps_commands.OperationController")
    @patch("services.software.flatpak_maintenance.FlatpakMaintenanceService")
    def test_cleanup_without_yes_only_reviews_and_explains_recovery(self, service_class, controller, context, _profile):
        from cli.commands.apps_commands import handle_apps
        from core.tasks.catalog import TaskContext
        context.return_value = TaskContext(variant=FedoraVariant.TRADITIONAL)
        service_class.return_value.unused.return_value = SimpleNamespace(available=True, digest="digest")
        instance = controller.return_value
        instance.prepare.return_value.plan.policy_decision.allowed = True
        output = []
        args = SimpleNamespace(apps_action="cleanup", installation="user", refs=["runtime/org.test.R/x86_64/1"], yes=False)
        self.assertEqual(handle_apps(args, False, Mock(), output.append), 0)
        self.assertIn("manual reinstallation", " ".join(output))
        self.assertIn("no automatic rollback", " ".join(output))
        instance.confirm.assert_not_called()
        instance.run.assert_not_called()
