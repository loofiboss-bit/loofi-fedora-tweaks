"""Haven daemon handler trust-boundary tests."""

import unittest
from unittest.mock import MagicMock, patch

from core.executor.action_result import ActionResult
from daemon.handlers.firewall_handler import FirewallHandler
from daemon.handlers.network_handler import NetworkHandler
from daemon.handlers.package_handler import PackageHandler
from daemon.handlers.service_handler import ServiceHandler


class TestDaemonReadPaths(unittest.TestCase):
    @patch("daemon.handlers.network_handler.NetworkUtils")
    def test_network_scan_is_still_read_only(self, network):
        network.scan_wifi_local.return_value = [("ssid", "80%", "WPA2", "Connected")]
        self.assertEqual(NetworkHandler.scan_wifi()[0]["ssid"], "ssid")

    @patch("daemon.handlers.firewall_handler.FirewallManager")
    def test_firewall_status_is_still_read_only(self, firewall):
        firewall.get_status_local.return_value.to_dict.return_value = {"running": True}
        self.assertTrue(FirewallHandler.get_status()["running"])

    @patch("daemon.handlers.package_handler.get_package_service")
    def test_package_search_is_still_read_only(self, get_service):
        get_service.return_value.search_local.return_value = ActionResult.ok("ok")
        self.assertTrue(PackageHandler.search("vim", 10)["success"])


class TestDaemonPlanOnlyMutations(unittest.TestCase):
    @patch("daemon.handlers.package_handler.create_plan")
    def test_single_package_install_creates_review_plan(self, create_plan):
        create_plan.return_value = {"plan_only": True, "auto_apply": False}
        payload = PackageHandler.install(["vim"])
        self.assertTrue(payload["plan_only"])
        self.assertFalse(payload["auto_apply"])
        create_plan.assert_called_once_with(
            "install-application", {"source": "fedora", "package_id": "vim"}
        )

    @patch("daemon.handlers.package_handler.create_manual_plan")
    def test_selected_package_update_is_manual_only(self, create_manual_plan):
        create_manual_plan.return_value = {"plan_only": True}
        self.assertTrue(PackageHandler.update(["vim"])["plan_only"])

    @patch("daemon.handlers.firewall_handler.create_manual_plan")
    def test_firewall_write_creates_plan_without_manager_call(self, create_manual_plan):
        create_manual_plan.return_value = {"plan_only": True}
        self.assertTrue(FirewallHandler.open_port("443", "tcp", "public", True)["plan_only"])
        create_manual_plan.assert_called_once()

    @patch("daemon.handlers.network_handler.create_manual_plan")
    def test_network_write_creates_plan_without_network_call(self, create_manual_plan):
        create_manual_plan.return_value = {"plan_only": True}
        self.assertTrue(NetworkHandler.apply_dns("wifi", "1.1.1.1")["plan_only"])

    @patch("daemon.handlers.service_handler.create_manual_plan")
    def test_service_write_creates_plan_without_service_manager_call(self, create_manual_plan):
        create_manual_plan.return_value = {"plan_only": True}
        self.assertTrue(ServiceHandler.stop_unit("sshd", "system")["plan_only"])


if __name__ == "__main__":
    unittest.main()
