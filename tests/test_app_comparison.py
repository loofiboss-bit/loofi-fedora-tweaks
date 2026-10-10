"""Snapshot-only app comparisons preserve exact identities and operation authority."""
import argparse
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.tasks.applications import ApplicationCatalog
from core.executor.action_result import ActionResult
from services.software.app_comparison import compare_installations, comparison_id
from services.software.installed_applications import InstalledApplication, InstalledApplicationService, InstalledInventory


def flatpak(installation="user", arch="x86_64", branch="stable"):
    return InstalledApplication("Firefox", "org.mozilla.firefox", "flatpak", installation,
                                f"app/org.mozilla.firefox/{arch}/{branch}", "1", "20 MB")


class AppComparisonTests(unittest.TestCase):
    def test_exact_scopes_branches_and_architectures_are_distinct(self):
        apps = (flatpak(), flatpak("system"), flatpak("work"), flatpak(branch="beta"), flatpak(arch="aarch64"))
        inventory = InstalledInventory(apps)
        report = compare_installations(inventory, "org.mozilla.firefox")
        self.assertEqual(set(report.installations), set(apps))
        self.assertEqual(inventory.applications, apps)

    def test_explicit_counterparts_do_not_match_similar_names(self):
        rpm = InstalledApplication("Browser", "firefox", "fedora", "system", "firefox")
        same_name = InstalledApplication("Firefox", "other", "fedora", "system", "other")
        other_id = InstalledApplication("Firefox", "org.test.firefox", "flatpak", "user", "app/org.test.firefox/x86_64/stable")
        report = compare_installations(InstalledInventory((flatpak(), rpm, same_name, other_id)), "org.mozilla.firefox")
        self.assertEqual(set(report.installations), {flatpak(), rpm})
        self.assertEqual(comparison_id(rpm), "org.mozilla.firefox")
        self.assertIsNone(comparison_id(same_name))

    def test_all_six_counterparts_are_explicit_catalog_metadata(self):
        catalog = ApplicationCatalog()
        for name in ("firefox", "thunderbird", "vlc", "gimp", "inkscape", "kdenlive"):
            self.assertEqual(catalog.get(name).metadata["rpm_counterparts"], (name,))

    def test_partial_source_failure_is_retained_without_losing_rows(self):
        report = compare_installations(InstalledInventory((flatpak(),), ("RPM read failed",), frozenset({"fedora"})), "org.mozilla.firefox")
        self.assertEqual(report.installations, (flatpak(),))
        self.assertEqual(report.to_dict()["unknown_sources"], ["fedora"])
        self.assertEqual(report.errors, ("RPM read failed",))

    @patch("services.software.rpm_desktop_applications.discover_rpm_desktop_applications")
    def test_declared_rpm_is_inventoried_even_without_desktop_entry(self, discover):
        discover.return_value = SimpleNamespace(names={}, errors=())
        probe = Mock(side_effect=[ActionResult(True, "ok", stdout=""), ActionResult(True, "ok", stdout="firefox\t1-2\t100\n")])
        inventory = InstalledApplicationService(probe=probe).snapshot()
        self.assertEqual(inventory.applications[0].app_id, "firefox")
        self.assertEqual(inventory.applications[0].source, "fedora")

    def test_invalid_id_rejected(self):
        for app_id in ("--user", "app/org.mozilla.firefox/x86_64/stable", "../bad", ""):
            with self.subTest(app_id=app_id), self.assertRaises(ValueError):
                compare_installations(InstalledInventory(), app_id)

    def test_cli_parser(self):
        from cli.parser_domains.apps import register_apps_command
        parser = argparse.ArgumentParser()
        register_apps_command(parser.add_subparsers())
        args = parser.parse_args(["apps", "compare", "org.mozilla.firefox", "--json"])
        self.assertEqual(args.app_id, "org.mozilla.firefox")
        self.assertTrue(args.json)

    @patch("cli.commands.apps_commands.detect_platform_profile")
    @patch("cli.commands.apps_commands.InstalledApplicationService")
    @patch("cli.commands.apps_commands.TaskContext.from_platform_profile")
    def test_cli_comparison_uses_one_snapshot_and_reports_partial_failure(self, context, service, profile):
        from cli.commands.apps_commands import handle_apps
        from core.tasks.catalog import TaskContext
        context.return_value = TaskContext()
        service.return_value.snapshot.return_value = InstalledInventory((flatpak(),), ("RPM failed",), frozenset({"fedora"}))
        output = Mock()
        code = handle_apps(SimpleNamespace(apps_action="compare", app_id="org.mozilla.firefox"), True, output, Mock())
        self.assertEqual(code, 1)
        service.return_value.snapshot.assert_called_once_with()
        self.assertEqual(output.call_args.args[0]["installations"][0]["ref"], flatpak().ref)


class AppComparisonPresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_dialog_only_routes_selected_identity_after_explicit_click(self):
        from ui.app_comparison import ApplicationComparisonDialog
        rpm = InstalledApplication("Firefox", "firefox", "fedora", "system", "firefox")
        dialog = ApplicationComparisonDialog(compare_installations(InstalledInventory((flatpak("work", branch="beta"), rpm)), "org.mozilla.firefox"))
        details, removals, native = [], [], []
        dialog.detailsRequested.connect(details.append)
        dialog.removalRequested.connect(removals.append)
        dialog.softwareManagerRequested.connect(lambda: native.append(True))
        for index in range(dialog.selection.count()):
            selected = dialog.selection.itemData(index)
            dialog.selection.setCurrentIndex(index)
            self.assertFalse(details or removals or native)
            if selected.source == "flatpak":
                dialog.details_button.click()
                dialog.remove_button.click()
                self.assertEqual(details.pop(), selected)
                self.assertEqual(removals.pop().ref, selected.ref)
            else:
                self.assertFalse(dialog.details_button.isEnabled())
                dialog.remove_button.click()
                self.assertTrue(native.pop())
        dialog.close()
        dialog.deleteLater()

    def test_card_comparison_reuses_inventory_and_closes_on_refresh(self):
        from PyQt6.QtWidgets import QPushButton
        from ui.installed_applications import InstalledApplicationsCard
        service = Mock()
        card = InstalledApplicationsCard(service=service)
        card.apply_inventory(InstalledInventory((flatpak(), flatpak("work"))))
        buttons = [button for button in card.findChildren(QPushButton) if button.text() == "Compare installations"]
        self.assertEqual(len(buttons), 2)
        buttons[0].click()
        self.assertEqual(len(card._comparison_dialogs), 1)
        service.snapshot.assert_not_called()
        service.details.assert_not_called()
        card.apply_inventory(InstalledInventory())
        self.assertFalse(card._comparison_dialogs)
        card.cleanup()
        card.deleteLater()
