"""Tests for Phase 6's normalized application workflow."""

import unittest
from unittest.mock import patch

from services.software.applications import ApplicationOperationService


class TestApplicationOperationService(unittest.TestCase):
    FLATPAK = {
        "name": "Example",
        "desc": "Example app",
        "cmd": "flatpak",
        "args": ["install", "-y", "flathub", "org.example.App"],
        "check_cmd": "flatpak list | grep org.example.App",
    }
    RPM = {
        "name": "Editor",
        "desc": "Text editor",
        "cmd": "pkexec",
        "args": ["dnf", "install", "-y", "editor"],
        "check_cmd": "rpm -q editor",
    }

    def test_flatpak_source_and_install_remove_are_one_primary_operation(self):
        app = ApplicationOperationService.describe(self.FLATPAK)
        install = ApplicationOperationService.operation(self.FLATPAK, installed=False)
        remove = ApplicationOperationService.operation(self.FLATPAK, installed=True)

        self.assertEqual(app.source, "Flathub (Flatpak)")
        self.assertEqual(install.arguments, ("install", "-y", "flathub", "org.example.App"))
        self.assertEqual(remove.arguments, ("uninstall", "-y", "org.example.App"))

    @patch("services.software.applications.SystemManager.is_atomic", return_value=False)
    @patch("utils.batch_ops.SystemManager.get_package_manager", return_value="dnf")
    def test_traditional_rpm_uses_existing_package_builder(self, _manager, _atomic):
        app = ApplicationOperationService.describe(self.RPM)
        operation = ApplicationOperationService.operation(self.RPM, installed=False)

        self.assertEqual(app.source, "Fedora RPM")
        self.assertEqual(operation.binary, "pkexec")
        self.assertIn("dnf", operation.arguments)
        self.assertFalse(operation.reboot_expected)

    @patch("services.software.applications.SystemManager.is_atomic", return_value=True)
    @patch("utils.batch_ops.SystemManager.get_package_manager", return_value="rpm-ostree")
    def test_atomic_rpm_uses_layering_and_explains_reboot(self, _manager, _atomic):
        app = ApplicationOperationService.describe(self.RPM)
        operation = ApplicationOperationService.operation(self.RPM, installed=False)

        self.assertIn("new deployment", app.explanation)
        self.assertEqual(operation.arguments[:2], ("rpm-ostree", "install"))
        self.assertTrue(operation.reboot_expected)

    def test_embedded_shell_repository_bootstrap_is_not_executed(self):
        entry = {
            "name": "Repository App",
            "cmd": "pkexec",
            "args": ["sh", "-c", "dnf config-manager addrepo && dnf install app"],
            "check_cmd": "rpm -q app",
        }

        app = ApplicationOperationService.describe(entry)

        self.assertFalse(app.available)
        self.assertIn("Repositories", app.explanation)
        with self.assertRaises(ValueError):
            ApplicationOperationService.operation(entry, installed=False)

    def test_vendor_rpm_source_is_explicit(self):
        entry = {
            "name": "Browser",
            "cmd": "pkexec",
            "args": ["dnf", "install", "-y", "https://example.test/browser.rpm"],
            "check_cmd": "rpm -q browser",
        }

        app = ApplicationOperationService.describe(entry)

        self.assertEqual(app.source, "Vendor RPM")
        self.assertEqual(app.package_id, "browser")


if __name__ == "__main__":
    unittest.main()
