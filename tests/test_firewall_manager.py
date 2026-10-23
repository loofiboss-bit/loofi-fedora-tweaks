"""
Tests for utils/firewall_manager.py
"""
# pylint: disable=protected-access

import os
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, patch

from services.security.firewall import (
    FirewallInfo,
    FirewallManager,
    FirewallResult,
    ZoneInfo,
)

sys.path.append(os.path.join(os.path.dirname(
    __file__), '..', 'loofi-fedora-tweaks'))


class TestFirewallInfo(unittest.TestCase):
    """Tests for the FirewallInfo dataclass."""

    def test_to_dict(self):
        """Serialization to dict works."""
        info = FirewallInfo(
            running=True, default_zone="public",
            active_zones={"public": ["eth0"]},
            ports=["80/tcp", "443/tcp"],
            services=["ssh", "http"],
            rich_rules=["rule family=ipv4 accept"],
        )
        d = info.to_dict()
        self.assertTrue(d["running"])
        self.assertEqual(d["default_zone"], "public")
        self.assertEqual(len(d["ports"]), 2)
        self.assertEqual(len(d["services"]), 2)
        self.assertEqual(len(d["rich_rules"]), 1)

    def test_to_dict_all_keys(self):
        """to_dict returns all expected keys."""
        d = FirewallInfo().to_dict()
        expected = {"running", "default_zone", "active_zones",
                    "ports", "services", "rich_rules"}
        self.assertEqual(set(d.keys()), expected)

    def test_defaults(self):
        """Default values are correct."""
        info = FirewallInfo()
        self.assertFalse(info.running)
        self.assertEqual(info.default_zone, "")
        self.assertEqual(info.ports, [])
        self.assertEqual(info.services, [])
        self.assertEqual(info.rich_rules, [])


class TestFirewallResult(unittest.TestCase):
    """Tests for FirewallResult dataclass."""

    def test_success(self):
        """Success result attributes."""
        r = FirewallResult(success=True, message="OK")
        self.assertTrue(r.success)

    def test_failure(self):
        """Failure result attributes."""
        r = FirewallResult(success=False, message="Error")
        self.assertFalse(r.success)


class TestZoneInfo(unittest.TestCase):
    """Tests for ZoneInfo dataclass."""

    def test_zone_info_attributes(self):
        """ZoneInfo initializes name and active attributes properly."""
        z = ZoneInfo(name="public", active=True)
        self.assertEqual(z.name, "public")
        self.assertTrue(z.active)

        z_inactive = ZoneInfo(name="work", active=False)
        self.assertEqual(z_inactive.name, "work")
        self.assertFalse(z_inactive.active)


class TestFirewallManagerAvailability(unittest.TestCase):
    """Tests for availability and running checks."""

    def setUp(self):
        FirewallManager._available_cached = None
        FirewallManager._available_cache_run_id = None

    @patch('services.security.firewall.subprocess.run')
    def test_is_available_true(self, mock_run):
        """Returns True when firewall-cmd exists."""
        mock_run.return_value = MagicMock(returncode=0)

        self.assertTrue(FirewallManager.is_available())

    @patch('services.security.firewall.subprocess.run')
    def test_is_available_false(self, mock_run):
        """Returns False when firewall-cmd not found."""
        mock_run.side_effect = OSError("Not found")

        self.assertFalse(FirewallManager.is_available())

    @patch('services.security.firewall.subprocess.run')
    def test_is_available_timeout(self, mock_run):
        """Returns False on timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd="firewall-cmd", timeout=5)

        self.assertFalse(FirewallManager.is_available())

    @patch('services.security.firewall.subprocess.run')
    def test_is_available_cached(self, mock_run):
        """Returns cached availability result on subsequent calls."""
        mock_run.return_value = MagicMock(returncode=0)

        self.assertTrue(FirewallManager.is_available())
        self.assertEqual(mock_run.call_count, 1)

        self.assertTrue(FirewallManager.is_available())
        self.assertEqual(mock_run.call_count, 1)

    @patch('services.security.firewall.subprocess.run')
    def test_is_running_true(self, mock_run):
        """Returns True when firewalld is running."""
        mock_run.return_value = MagicMock(returncode=0, stdout="running\n")

        self.assertTrue(FirewallManager.is_running())

    @patch('services.security.firewall.subprocess.run')
    def test_is_running_false(self, mock_run):
        """Returns False when firewalld is not running."""
        mock_run.return_value = MagicMock(returncode=1, stdout="not running\n")

        self.assertFalse(FirewallManager.is_running())

    @patch('services.security.firewall.subprocess.run')
    def test_is_running_os_error(self, mock_run):
        """Returns False on OSError."""
        mock_run.side_effect = OSError("No such file")

        self.assertFalse(FirewallManager.is_running())

    @patch('services.security.firewall.daemon_client.call_json')
    def test_is_running_daemon_first(self, mock_call_json):
        """Uses daemon status payload when available."""
        mock_call_json.return_value = {"running": True}

        self.assertTrue(FirewallManager.is_running())
        mock_call_json.assert_called_once_with("FirewallGetStatus")

    @patch('services.security.firewall.subprocess.run')
    @patch('services.security.firewall.daemon_client.call_json')
    def test_is_running_falls_back_to_local(self, mock_call_json, mock_run):
        """Falls back to local check when daemon payload is unavailable."""
        mock_call_json.return_value = None
        mock_run.return_value = MagicMock(returncode=0, stdout="running\n")

        self.assertTrue(FirewallManager.is_running())
        mock_call_json.assert_called_once_with("FirewallGetStatus")
        mock_run.assert_called_once()


class TestFirewallManagerStatus(unittest.TestCase):
    """Tests for FirewallManager status functions."""

    @patch('services.security.firewall.daemon_client.call_json')
    def test_get_status_running(self, mock_call_json):
        """Returns full status when daemon payload is available."""
        mock_call_json.return_value = {
            "running": True,
            "default_zone": "public",
            "active_zones": {"public": ["eth0"]},
            "ports": ["80/tcp"],
            "services": ["ssh", "http"],
            "rich_rules": [],
        }

        info = FirewallManager.get_status()

        self.assertTrue(info.running)
        self.assertEqual(info.default_zone, "public")
        self.assertEqual(info.ports, ["80/tcp"])
        self.assertEqual(info.services, ["ssh", "http"])
        mock_call_json.assert_called_once_with("FirewallGetStatus")

    @patch('services.security.firewall.daemon_client.call_json')
    def test_get_status_not_running(self, mock_call_json):
        """Returns minimal status when daemon reports not running."""
        mock_call_json.return_value = {"running": False}

        info = FirewallManager.get_status()

        self.assertFalse(info.running)
        self.assertEqual(info.default_zone, "")
        self.assertEqual(info.ports, [])
        mock_call_json.assert_called_once_with("FirewallGetStatus")

    @patch('services.security.firewall.FirewallManager._get_status_legacy')
    @patch('services.security.firewall.daemon_client.call_json')
    def test_get_status_non_dict_fallback(self, mock_call_json, mock_legacy):
        """Falls back to _get_status_legacy when daemon returns non-dict."""
        mock_call_json.return_value = None
        mock_legacy.return_value = FirewallInfo(running=False)

        info = FirewallManager.get_status()

        self.assertFalse(info.running)
        mock_legacy.assert_called_once()

    @patch('services.security.firewall.FirewallManager.list_rich_rules')
    @patch('services.security.firewall.FirewallManager.list_services')
    @patch('services.security.firewall.FirewallManager.list_ports')
    @patch('services.security.firewall.FirewallManager.get_active_zones')
    @patch('services.security.firewall.FirewallManager.get_default_zone')
    @patch('services.security.firewall.FirewallManager.is_running_local')
    def test_get_status_local_running(
        self, mock_is_running, mock_default_zone, mock_active_zones,
        mock_ports, mock_services, mock_rich_rules
    ):
        """get_status_local populates all fields when running."""
        mock_is_running.return_value = True
        mock_default_zone.return_value = "public"
        mock_active_zones.return_value = {"public": ["eth0"]}
        mock_ports.return_value = ["80/tcp"]
        mock_services.return_value = ["ssh"]
        mock_rich_rules.return_value = ["rule"]

        info = FirewallManager.get_status_local()

        self.assertTrue(info.running)
        self.assertEqual(info.default_zone, "public")
        self.assertEqual(info.active_zones, {"public": ["eth0"]})
        self.assertEqual(info.ports, ["80/tcp"])
        self.assertEqual(info.services, ["ssh"])
        self.assertEqual(info.rich_rules, ["rule"])

    @patch('services.security.firewall.FirewallManager.is_running_local')
    def test_get_status_local_not_running(self, mock_is_running):
        """get_status_local returns default FirewallInfo when not running."""
        mock_is_running.return_value = False

        info = FirewallManager.get_status_local()

        self.assertFalse(info.running)
        self.assertEqual(info.default_zone, "")

    @patch('services.security.firewall.FirewallManager.is_running_local')
    def test_get_status_legacy_not_running(self, mock_is_running):
        """_get_status_legacy returns default FirewallInfo when not running."""
        mock_is_running.return_value = False

        info = FirewallManager._get_status_legacy()

        self.assertFalse(info.running)
        self.assertEqual(info.default_zone, "")


class TestFirewallManagerZones(unittest.TestCase):
    """Tests for zone operations."""

    @patch('services.security.firewall.subprocess.run')
    def test_get_default_zone(self, mock_run):
        """Returns default zone name."""
        mock_run.return_value = MagicMock(returncode=0, stdout="public\n")

        zone = FirewallManager.get_default_zone()

        self.assertEqual(zone, "public")

    @patch('services.security.firewall.subprocess.run')
    def test_get_default_zone_failure(self, mock_run):
        """Returns empty string on failure."""
        mock_run.return_value = MagicMock(returncode=1, stdout="")

        zone = FirewallManager.get_default_zone()

        self.assertEqual(zone, "")

    @patch('services.security.firewall.subprocess.run')
    def test_get_zones(self, mock_run):
        """Lists all available zones."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "block dmz drop external home internal "
                "nm-shared public trusted work\n"
            ),
        )

        zones = FirewallManager.get_zones()

        self.assertIn("public", zones)
        self.assertIn("trusted", zones)
        self.assertEqual(len(zones), 10)

    @patch('services.security.firewall.subprocess.run')
    def test_get_zones_failure(self, mock_run):
        """Returns empty list on failure."""
        mock_run.return_value = MagicMock(returncode=1, stdout="")

        zones = FirewallManager.get_zones()

        self.assertEqual(zones, [])

    @patch('services.security.firewall.subprocess.run')
    def test_get_active_zones(self, mock_run):
        """Parses active zones with interfaces."""
        output = (
            "public\n  interfaces: eth0 wlan0\n"
            "trusted\n  interfaces: virbr0\n"
        )
        mock_run.return_value = MagicMock(returncode=0, stdout=output)

        zones = FirewallManager.get_active_zones()

        self.assertIn("public", zones)
        self.assertIn("eth0", zones["public"])
        self.assertIn("wlan0", zones["public"])
        self.assertIn("trusted", zones)

    @patch('services.security.firewall.subprocess.run')
    def test_get_active_zones_with_sources(self, mock_run):
        """Parses active zones with sources and interfaces."""
        output = (
            "\n"
            "public\n"
            "  interfaces: eth0\n"
            "  sources: 192.168.1.0/24\n"
        )
        mock_run.return_value = MagicMock(returncode=0, stdout=output)

        zones = FirewallManager.get_active_zones_local()

        self.assertIn("public", zones)
        self.assertIn("eth0", zones["public"])
        self.assertIn("192.168.1.0/24", zones["public"])

    @patch('services.security.firewall.subprocess.run')
    def test_get_active_zones_empty(self, mock_run):
        """Returns empty dict when no active zones."""
        mock_run.return_value = MagicMock(returncode=0, stdout="")

        zones = FirewallManager.get_active_zones()

        self.assertEqual(zones, {})

    @patch('services.security.firewall.subprocess.run')
    def test_get_active_zones_error(self, mock_run):
        """Returns empty dict on nonzero exit or exception."""
        mock_run.return_value = MagicMock(returncode=1, stdout="error")

        zones = FirewallManager.get_active_zones_local()

        self.assertEqual(zones, {})

        mock_run.side_effect = OSError("failed")
        zones = FirewallManager.get_active_zones_local()
        self.assertEqual(zones, {})

    @patch('services.security.firewall.daemon_client.call_json')
    def test_get_active_zones_daemon_invalid(self, mock_call_json):
        """Handles invalid dictionary keys/values from daemon gracefully."""
        mock_call_json.return_value = {
            123: ["eth0"],
            "public": ["eth0", 80],
            "trusted": "not_a_list",
        }

        zones = FirewallManager.get_active_zones()

        self.assertNotIn(123, zones)
        self.assertEqual(zones["public"], ["eth0", "80"])
        self.assertEqual(zones["trusted"], [])

    @patch('services.security.firewall.FirewallManager.get_active_zones')
    @patch('services.security.firewall.FirewallManager.get_zones')
    def test_list_zones_cli_compat(self, mock_get_zones, mock_get_active_zones):
        """list_zones returns ZoneInfo list with active state."""
        mock_get_zones.return_value = ["public", "trusted", "work"]
        mock_get_active_zones.return_value = {"public": ["eth0"]}

        zone_infos = FirewallManager.list_zones()

        self.assertEqual(len(zone_infos), 3)
        self.assertTrue(zone_infos[0].active)
        self.assertEqual(zone_infos[0].name, "public")
        self.assertFalse(zone_infos[1].active)
        self.assertEqual(zone_infos[1].name, "trusted")

    @patch('services.security.firewall.subprocess.run')
    def test_set_default_zone_success(self, mock_run):
        """Set default zone returns success."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        result = FirewallManager.set_default_zone("trusted")

        self.assertTrue(result.success)
        self.assertIn("trusted", result.message)

    @patch('services.security.firewall.subprocess.run')
    def test_set_default_zone_failure(self, mock_run):
        """Set default zone returns failure on error."""
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="Invalid zone"
        )

        result = FirewallManager.set_default_zone("bogus")

        self.assertFalse(result.success)


class TestFirewallManagerPorts(unittest.TestCase):
    """Tests for port operations."""

    @patch('services.security.firewall.subprocess.run')
    def test_list_ports(self, mock_run):
        """Lists open ports."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="80/tcp 443/tcp 8080/tcp\n"
        )

        ports = FirewallManager.list_ports()

        self.assertEqual(len(ports), 3)
        self.assertIn("80/tcp", ports)

    @patch('services.security.firewall.subprocess.run')
    def test_list_ports_empty(self, mock_run):
        """Returns empty list when no ports open."""
        mock_run.return_value = MagicMock(returncode=0, stdout="\n")

        ports = FirewallManager.list_ports()

        self.assertEqual(ports, [])

    @patch('services.security.firewall.subprocess.run')
    def test_list_ports_with_zone(self, mock_run):
        """Passes zone parameter."""
        mock_run.return_value = MagicMock(returncode=0, stdout="")

        FirewallManager.list_ports(zone="trusted")

        cmd = mock_run.call_args[0][0]
        self.assertIn("--zone", cmd)
        self.assertIn("trusted", cmd)

    @patch('services.security.firewall.daemon_client.call_json')
    def test_list_services_daemon_first(self, mock_call_json):
        """list_services uses daemon client response when available."""
        mock_call_json.return_value = ["ssh", "http"]

        services = FirewallManager.list_services("public")

        self.assertEqual(services, ["ssh", "http"])
        mock_call_json.assert_called_once_with("FirewallListServices", "public")

    @patch('services.security.firewall.subprocess.run')
    def test_list_services_local_oserror(self, mock_run):
        """list_services_local handles OSError gracefully."""
        mock_run.side_effect = OSError("error")

        services = FirewallManager.list_services_local()

        self.assertEqual(services, [])

    @patch('services.security.firewall.subprocess.run')
    def test_remove_service_failure(self, mock_run):
        """remove_service returns failure when firewall-cmd fails."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Not active")

        result = FirewallManager.remove_service("http")

        self.assertFalse(result.success)
        self.assertIn("Failed to remove http: Not active", result.message)

    @patch('services.security.firewall.subprocess.run')
    def test_remove_service_timeout(self, mock_run):
        """remove_service handles timeout exception."""
        mock_run.side_effect = subprocess.TimeoutExpired("firewall-cmd", 15)

        result = FirewallManager.remove_service("http")

        self.assertFalse(result.success)
        self.assertIn("Error:", result.message)

    @patch('services.security.firewall.FirewallManager._reload')
    @patch('services.security.firewall.subprocess.run')
    def test_open_port_success(self, mock_run, mock_reload):
        """Open port returns success and calls reload."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        mock_reload.return_value = True

        result = FirewallManager.open_port("8080", "tcp")

        self.assertTrue(result.success)
        self.assertIn("8080/tcp", result.message)
        mock_reload.assert_called_once()

    @patch('services.security.firewall.subprocess.run')
    def test_open_port_failure(self, mock_run):
        """Open port returns failure on error."""
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="Already open"
        )

        result = FirewallManager.open_port("8080")

        self.assertFalse(result.success)

    @patch('services.security.firewall.subprocess.run')
    def test_open_port_uses_pkexec(self, mock_run):
        """Open port command uses pkexec."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        FirewallManager.open_port("8080", permanent=False)

        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd[0], "pkexec")

    @patch('services.security.firewall.FirewallManager._reload')
    @patch('services.security.firewall.subprocess.run')
    def test_close_port_success(self, mock_run, mock_reload):
        """Close port returns success."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        mock_reload.return_value = True

        result = FirewallManager.close_port("8080", "tcp")

        self.assertTrue(result.success)
        self.assertIn("8080/tcp", result.message)

    @patch('services.security.firewall.subprocess.run')
    def test_open_port_timeout(self, mock_run):
        """Open port returns failure on timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd="firewall-cmd", timeout=15)

        result = FirewallManager.open_port("8080")

        self.assertFalse(result.success)
        self.assertIn("Error", result.message)

    @patch('services.security.firewall.subprocess.run')
    def test_open_port_non_permanent(self, mock_run):
        """Non-permanent port doesn't add --permanent flag."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        FirewallManager.open_port("8080", permanent=False)

        cmd = mock_run.call_args[0][0]
        self.assertNotIn("--permanent", cmd)

    @patch('services.security.firewall.daemon_client.call_json')
    def test_list_ports_daemon_first(self, mock_call_json):
        """list_ports uses daemon client response when available."""
        mock_call_json.return_value = ["80/tcp", 443]

        ports = FirewallManager.list_ports("public")

        self.assertEqual(ports, ["80/tcp", "443"])
        mock_call_json.assert_called_once_with("FirewallListPorts", "public")

    @patch('services.security.firewall.subprocess.run')
    def test_list_ports_local_oserror(self, mock_run):
        """list_ports_local handles OSError gracefully."""
        mock_run.side_effect = OSError("error")

        ports = FirewallManager.list_ports_local()

        self.assertEqual(ports, [])

    @patch('services.security.firewall.FirewallManager.open_port')
    def test_add_port_cli_alias(self, mock_open_port):
        """add_port parses port/protocol and delegates to open_port."""
        mock_open_port.return_value = FirewallResult(True, "OK")

        res1 = FirewallManager.add_port("8080/udp", zone="public")
        mock_open_port.assert_called_with("8080", "udp", "public")
        self.assertTrue(res1.success)

        res2 = FirewallManager.add_port("8080")
        mock_open_port.assert_called_with("8080", "tcp", "")
        self.assertTrue(res2.success)

    @patch('services.security.firewall.FirewallManager.close_port')
    def test_remove_port_cli_alias(self, mock_close_port):
        """remove_port parses port/protocol and delegates to close_port."""
        mock_close_port.return_value = FirewallResult(True, "OK")

        res1 = FirewallManager.remove_port("8080/udp", zone="public")
        mock_close_port.assert_called_with("8080", "udp", "public")
        self.assertTrue(res1.success)

        res2 = FirewallManager.remove_port("8080")
        mock_close_port.assert_called_with("8080", "tcp", "")
        self.assertTrue(res2.success)

    @patch('services.security.firewall.subprocess.run')
    def test_close_port_failure_message(self, mock_run):
        """close_port returns error message when command fails."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Not open")

        result = FirewallManager.close_port("8080")

        self.assertFalse(result.success)
        self.assertIn("Failed to close 8080/tcp: Not open", result.message)

    @patch('services.security.firewall.subprocess.run')
    def test_close_port_timeout(self, mock_run):
        """close_port handles timeout exception."""
        mock_run.side_effect = subprocess.TimeoutExpired("firewall-cmd", 15)

        result = FirewallManager.close_port("8080")

        self.assertFalse(result.success)
        self.assertIn("Error:", result.message)


class TestFirewallManagerServices(unittest.TestCase):
    """Tests for service operations."""

    @patch('services.security.firewall.subprocess.run')
    def test_list_services(self, mock_run):
        """Lists allowed services."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="dhcpv6-client http ssh\n"
        )

        services = FirewallManager.list_services()

        self.assertIn("http", services)
        self.assertIn("ssh", services)

    @patch('services.security.firewall.subprocess.run')
    def test_list_services_empty(self, mock_run):
        """Returns empty list when no services."""
        mock_run.return_value = MagicMock(returncode=0, stdout="\n")

        services = FirewallManager.list_services()

        self.assertEqual(services, [])

    @patch('services.security.firewall.subprocess.run')
    def test_get_available_services(self, mock_run):
        """Lists all known services."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "dhcp dns ftp http https imap imaps "
                "nfs ntp pop3 samba ssh\n"
            ),
        )

        services = FirewallManager.get_available_services()

        self.assertIn("http", services)
        self.assertIn("ssh", services)
        self.assertGreater(len(services), 5)

    @patch('services.security.firewall.subprocess.run')
    def test_get_available_services_failure(self, mock_run):
        """Returns empty list on firewall-cmd failure.

        v2.11.0 TASK-006 contract.
        """
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="Error")

        services = FirewallManager.get_available_services()

        self.assertEqual(services, [])

    @patch('services.security.firewall.subprocess.run')
    def test_get_available_services_timeout(self, mock_run):
        """Returns empty list on timeout (v2.11.0 TASK-006 contract)."""
        mock_run.side_effect = subprocess.TimeoutExpired("firewall-cmd", 5)

        services = FirewallManager.get_available_services()

        self.assertEqual(services, [])

    @patch('services.security.firewall.FirewallManager._reload')
    @patch('services.security.firewall.subprocess.run')
    def test_add_service_success(self, mock_run, mock_reload):
        """Add service returns success."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        mock_reload.return_value = True

        result = FirewallManager.add_service("http")

        self.assertTrue(result.success)
        self.assertIn("http", result.message)

    @patch('services.security.firewall.subprocess.run')
    def test_add_service_failure(self, mock_run):
        """Add service returns failure on error."""
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="Invalid service"
        )

        result = FirewallManager.add_service("bogus")

        self.assertFalse(result.success)

    @patch('services.security.firewall.FirewallManager._reload')
    @patch('services.security.firewall.subprocess.run')
    def test_remove_service_success(self, mock_run, mock_reload):
        """Remove service returns success."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        mock_reload.return_value = True

        result = FirewallManager.remove_service("http")

        self.assertTrue(result.success)
        self.assertIn("http", result.message)

    @patch('services.security.firewall.subprocess.run')
    def test_add_service_uses_pkexec(self, mock_run):
        """Add service uses pkexec."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        FirewallManager.add_service("http", permanent=False)

        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd[0], "pkexec")

    @patch('services.security.firewall.subprocess.run')
    def test_add_service_with_zone(self, mock_run):
        """Add service passes zone parameter."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        FirewallManager.add_service("http", zone="trusted", permanent=False)

        cmd = mock_run.call_args[0][0]
        self.assertIn("--zone", cmd)
        self.assertIn("trusted", cmd)


class TestFirewallManagerRichRules(unittest.TestCase):
    """Tests for rich rule operations."""

    @patch('services.security.firewall.subprocess.run')
    def test_list_rich_rules(self, mock_run):
        """Lists rich rules."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                'rule family="ipv4" '
                'source address="192.168.1.0/24" accept\n'
            ),
        )

        rules = FirewallManager.list_rich_rules()

        self.assertEqual(len(rules), 1)
        self.assertIn("192.168.1.0/24", rules[0])

    @patch('services.security.firewall.subprocess.run')
    def test_list_rich_rules_empty(self, mock_run):
        """Returns empty list when no rich rules."""
        mock_run.return_value = MagicMock(returncode=0, stdout="\n")

        rules = FirewallManager.list_rich_rules()

        self.assertEqual(rules, [])

    @patch('services.security.firewall.FirewallManager._reload')
    @patch('services.security.firewall.subprocess.run')
    def test_add_rich_rule_success(self, mock_run, mock_reload):
        """Add rich rule returns success."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        mock_reload.return_value = True

        result = FirewallManager.add_rich_rule('rule family="ipv4" accept')

        self.assertTrue(result.success)
        self.assertIn("rich rule", result.message)

    @patch('services.security.firewall.subprocess.run')
    def test_add_rich_rule_failure(self, mock_run):
        """Add rich rule returns failure on invalid rule."""
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="Invalid rule"
        )

        result = FirewallManager.add_rich_rule("bad rule")

        self.assertFalse(result.success)

    @patch('services.security.firewall.FirewallManager._reload')
    @patch('services.security.firewall.subprocess.run')
    def test_remove_rich_rule_success(self, mock_run, mock_reload):
        """Remove rich rule returns success."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        mock_reload.return_value = True

        result = FirewallManager.remove_rich_rule('rule family="ipv4" accept')

        self.assertTrue(result.success)


class TestFirewallManagerToggle(unittest.TestCase):
    """Tests for start/stop firewall."""

    @patch('services.security.firewall.subprocess.run')
    def test_start_firewall_success(self, mock_run):
        """Start firewalld returns success."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        result = FirewallManager.start_firewall()

        self.assertTrue(result.success)
        self.assertIn("started", result.message)

    @patch('services.security.firewall.subprocess.run')
    def test_start_firewall_failure(self, mock_run):
        """Start firewalld returns failure."""
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="Failed"
        )

        result = FirewallManager.start_firewall()

        self.assertFalse(result.success)

    @patch('services.security.firewall.subprocess.run')
    def test_stop_firewall_success(self, mock_run):
        """Stop firewalld returns success."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        result = FirewallManager.stop_firewall()

        self.assertTrue(result.success)
        self.assertIn("stopped", result.message)

    @patch('services.security.firewall.subprocess.run')
    def test_stop_firewall_failure(self, mock_run):
        """Stop firewalld returns failure."""
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="Failed"
        )

        result = FirewallManager.stop_firewall()

        self.assertFalse(result.success)

    @patch('services.security.firewall.subprocess.run')
    def test_start_firewall_uses_pkexec(self, mock_run):
        """Start firewall uses pkexec via PrivilegedCommand."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        FirewallManager.start_firewall()

        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd[0], "pkexec")

    @patch('services.security.firewall.subprocess.run')
    def test_start_firewall_timeout(self, mock_run):
        """Start firewall returns failure on timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd="systemctl", timeout=15)

        result = FirewallManager.start_firewall()

        self.assertFalse(result.success)
        self.assertIn("Error", result.message)


class TestFirewallManagerReload(unittest.TestCase):
    """Tests for internal _reload method."""

    @patch('services.security.firewall.subprocess.run')
    def test_reload_success(self, mock_run):
        """Reload returns True on success."""
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        self.assertTrue(FirewallManager._reload())

    @patch('services.security.firewall.subprocess.run')
    def test_reload_failure(self, mock_run):
        """Reload returns False on failure."""
        mock_run.return_value = MagicMock(returncode=1, stderr="Failed")

        self.assertFalse(FirewallManager._reload())

    @patch('services.security.firewall.subprocess.run')
    def test_reload_timeout(self, mock_run):
        """Reload returns False on timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd="firewall-cmd", timeout=15)

        self.assertFalse(FirewallManager._reload())

    @patch('services.security.firewall.FirewallManager._reload')
    def test_reload_public_method(self, mock_reload):
        """reload public method returns FirewallResult based on _reload."""
        mock_reload.return_value = True
        res = FirewallManager.reload()
        self.assertTrue(res.success)
        self.assertEqual(res.message, "Reloaded firewall")

        mock_reload.return_value = False
        res2 = FirewallManager.reload()
        self.assertFalse(res2.success)
        self.assertEqual(res2.message, "Failed to reload firewall")

    @patch('services.security.firewall.FirewallManager._reload')
    def test_reload_local_alias(self, mock_reload):
        """_reload_local delegates to _reload."""
        mock_reload.return_value = True
        self.assertTrue(FirewallManager._reload_local())
        mock_reload.assert_called_once()


class TestFirewallDaemonFirstReads(unittest.TestCase):
    """Tests daemon-first behavior for selected firewall read operations."""

    @patch('services.security.firewall.subprocess.run')
    @patch('services.security.firewall.daemon_client.call_json')
    def test_get_default_zone_prefers_daemon(self, mock_call_json, mock_run):
        mock_call_json.return_value = "public"
        zone = FirewallManager.get_default_zone()
        self.assertEqual(zone, "public")
        mock_call_json.assert_called_once_with("FirewallGetDefaultZone")
        mock_run.assert_not_called()

    @patch('services.security.firewall.subprocess.run')
    @patch('services.security.firewall.daemon_client.call_json')
    def test_get_zones_prefers_daemon(self, mock_call_json, mock_run):
        mock_call_json.return_value = ["public", "trusted"]
        zones = FirewallManager.get_zones()
        self.assertEqual(zones, ["public", "trusted"])
        mock_call_json.assert_called_once_with("FirewallGetZones")
        mock_run.assert_not_called()

    @patch('services.security.firewall.subprocess.run')
    @patch('services.security.firewall.daemon_client.call_json')
    def test_get_active_zones_prefers_daemon(self, mock_call_json, mock_run):
        mock_call_json.return_value = {"public": ["eth0"]}
        zones = FirewallManager.get_active_zones()
        self.assertEqual(zones, {"public": ["eth0"]})
        mock_call_json.assert_called_once_with("FirewallGetActiveZones")
        mock_run.assert_not_called()

    @patch('services.security.firewall.subprocess.run')
    @patch('services.security.firewall.daemon_client.call_json')
    def test_list_rich_rules_prefers_daemon(self, mock_call_json, mock_run):
        mock_call_json.return_value = ['rule family="ipv4" accept']
        rules = FirewallManager.list_rich_rules()
        self.assertEqual(rules, ['rule family="ipv4" accept'])
        mock_call_json.assert_called_once_with("FirewallListRichRules", "")
        mock_run.assert_not_called()


class TestFirewallCommandConstruction(unittest.TestCase):
    """Tests for PrivilegedCommand integration in firewall local
    mutators (v2.11.0 TASK-005/008).
    """

    @patch('services.security.firewall.PrivilegedCommand.execute_and_log')
    @patch('services.security.firewall.PrivilegedCommand.firewall_cmd')
    def test_set_default_zone_local_uses_privileged_command(
        self, mock_firewall_cmd, mock_execute
    ):
        """set_default_zone_local uses PrivilegedCommand.firewall_cmd
        builder.
        """
        mock_firewall_cmd.return_value = (
            "pkexec",
            ["firewall-cmd", "--set-default-zone=public"],
            "Setting zone..."
        )
        mock_execute.return_value = MagicMock(returncode=0, stderr="")

        result = FirewallManager.set_default_zone_local("public")

        mock_firewall_cmd.assert_called_once_with(
            "--set-default-zone=public"
        )
        mock_execute.assert_called_once()
        self.assertTrue(result.success)

    @patch('services.security.firewall.FirewallManager._reload')
    @patch('services.security.firewall.PrivilegedCommand.execute_and_log')
    @patch('services.security.firewall.PrivilegedCommand.firewall_cmd')
    def test_add_rich_rule_local_uses_privileged_command(
        self, mock_firewall_cmd, mock_execute, mock_reload
    ):
        """add_rich_rule_local uses PrivilegedCommand.firewall_cmd
        builder.
        """
        rule = 'rule family="ipv4" accept'
        mock_firewall_cmd.return_value = (
            "pkexec",
            ["firewall-cmd", f"--add-rich-rule={rule}", "--permanent"],
            "Adding rule..."
        )
        mock_execute.return_value = MagicMock(returncode=0, stderr="")
        mock_reload.return_value = True

        result = FirewallManager.add_rich_rule_local(rule, permanent=True)

        # Verify firewall_cmd was called with correct args
        call_args = mock_firewall_cmd.call_args[0]
        self.assertIn(f"--add-rich-rule={rule}", call_args)
        self.assertIn("--permanent", call_args)
        mock_execute.assert_called_once()
        self.assertTrue(result.success)

    @patch('services.security.firewall.FirewallManager._reload')
    @patch('services.security.firewall.PrivilegedCommand.execute_and_log')
    @patch('services.security.firewall.PrivilegedCommand.firewall_cmd')
    def test_remove_rich_rule_local_uses_privileged_command(
        self, mock_firewall_cmd, mock_execute, mock_reload
    ):
        """remove_rich_rule_local uses PrivilegedCommand.firewall_cmd
        builder.
        """
        rule = 'rule family="ipv4" accept'
        mock_firewall_cmd.return_value = (
            "pkexec",
            ["firewall-cmd", f"--remove-rich-rule={rule}", "--permanent"],
            "Removing rule..."
        )
        mock_execute.return_value = MagicMock(returncode=0, stderr="")
        mock_reload.return_value = True

        result = FirewallManager.remove_rich_rule_local(
            rule, permanent=True
        )

        # Verify firewall_cmd was called with correct args
        call_args = mock_firewall_cmd.call_args[0]
        self.assertIn(f"--remove-rich-rule={rule}", call_args)
        self.assertIn("--permanent", call_args)
        mock_execute.assert_called_once()
        self.assertTrue(result.success)

    @patch('services.security.firewall.PrivilegedCommand.execute_and_log')
    @patch('services.security.firewall.PrivilegedCommand.firewall_reload')
    def test_reload_uses_privileged_command_firewall_reload(
        self, mock_firewall_reload, mock_execute
    ):
        """_reload uses PrivilegedCommand.firewall_reload builder."""
        mock_firewall_reload.return_value = (
            "pkexec", ["firewall-cmd", "--reload"], "Reloading..."
        )
        mock_execute.return_value = MagicMock(returncode=0, stderr="")

        result = FirewallManager._reload()  # noqa

        mock_firewall_reload.assert_called_once()
        mock_execute.assert_called_once()
        self.assertTrue(result)


class TestFirewallTimeoutBehavior(unittest.TestCase):
    """Tests for timeout parameter enforcement in firewall operations
    (v2.11.0 TASK-005/008).
    """

    @patch('services.security.firewall.PrivilegedCommand.execute_and_log')
    @patch('services.security.firewall.PrivilegedCommand.firewall_cmd')
    def test_set_default_zone_local_passes_timeout(
        self, mock_firewall_cmd, mock_execute
    ):
        """set_default_zone_local passes timeout=15 to execute_and_log."""
        mock_firewall_cmd.return_value = (
            "pkexec",
            ["firewall-cmd", "--set-default-zone=public"],
            "desc"
        )
        mock_execute.return_value = MagicMock(returncode=0, stderr="")

        FirewallManager.set_default_zone_local("public")

        mock_execute.assert_called_once()
        call_kwargs = mock_execute.call_args[1]
        self.assertEqual(call_kwargs.get('timeout'), 15)

    @patch('services.security.firewall.FirewallManager._reload')
    @patch('services.security.firewall.PrivilegedCommand.execute_and_log')
    @patch('services.security.firewall.PrivilegedCommand.firewall_cmd')
    def test_add_rich_rule_local_passes_timeout(
        self, mock_firewall_cmd, mock_execute, mock_reload
    ):
        """add_rich_rule_local passes timeout=15 to execute_and_log."""
        mock_firewall_cmd.return_value = (
            "pkexec", ["firewall-cmd"], "desc"
        )
        mock_execute.return_value = MagicMock(returncode=0, stderr="")
        mock_reload.return_value = True

        FirewallManager.add_rich_rule_local('rule family="ipv4" accept')

        mock_execute.assert_called_once()
        call_kwargs = mock_execute.call_args[1]
        self.assertEqual(call_kwargs.get('timeout'), 15)

    @patch('services.security.firewall.PrivilegedCommand.execute_and_log')
    @patch('services.security.firewall.PrivilegedCommand.firewall_reload')
    def test_reload_passes_timeout(
        self, mock_firewall_reload, mock_execute
    ):
        """_reload passes timeout=15 to execute_and_log."""
        mock_firewall_reload.return_value = (
            "pkexec", ["firewall-cmd", "--reload"], "desc"
        )
        mock_execute.return_value = MagicMock(returncode=0, stderr="")

        FirewallManager._reload()  # noqa

        mock_execute.assert_called_once()
        call_kwargs = mock_execute.call_args[1]
        self.assertEqual(call_kwargs.get('timeout'), 15)

    @patch('services.security.firewall.PrivilegedCommand.execute_and_log')
    @patch('services.security.firewall.PrivilegedCommand.firewall_cmd')
    def test_set_default_zone_local_handles_timeout_error(
        self, mock_firewall_cmd, mock_execute
    ):
        """set_default_zone_local handles CommandTimeoutError."""
        from utils.errors import CommandTimeoutError
        mock_firewall_cmd.return_value = (
            "pkexec", ["firewall-cmd"], "desc"
        )
        mock_execute.side_effect = CommandTimeoutError(
            cmd="firewall-cmd", timeout=15
        )

        result = FirewallManager.set_default_zone_local("public")

        self.assertFalse(result.success)
        self.assertIn("Error", result.message)


class TestFirewallDaemonFirstWrites(unittest.TestCase):
    """Tests daemon-first behavior for selected firewall write operations."""

    @patch('services.security.firewall.subprocess.run')
    @patch('services.security.firewall.daemon_client.call_json')
    def test_set_default_zone_prefers_daemon(self, mock_call_json, mock_run):
        mock_call_json.return_value = {"success": True, "message": "ok"}
        result = FirewallManager.set_default_zone("public")
        self.assertTrue(result.success)
        self.assertEqual(result.message, "ok")
        mock_call_json.assert_called_once_with(
            "FirewallSetDefaultZone", "public")
        mock_run.assert_not_called()

    @patch('services.security.firewall.subprocess.run')
    @patch('services.security.firewall.daemon_client.call_json')
    def test_add_service_prefers_daemon(self, mock_call_json, mock_run):
        mock_call_json.return_value = {"success": True, "message": "added"}
        result = FirewallManager.add_service(
            "http", zone="trusted", permanent=False)
        self.assertTrue(result.success)
        self.assertEqual(result.message, "added")
        mock_call_json.assert_called_once_with(
            "FirewallAddService", "http", "trusted", False)
        mock_run.assert_not_called()

    @patch('services.security.firewall.subprocess.run')
    @patch('services.security.firewall.daemon_client.call_json')
    def test_remove_service_prefers_daemon(self, mock_call_json, mock_run):
        mock_call_json.return_value = {"success": True, "message": "removed"}
        result = FirewallManager.remove_service(
            "http", zone="trusted", permanent=False)
        self.assertTrue(result.success)
        self.assertEqual(result.message, "removed")
        mock_call_json.assert_called_once_with(
            "FirewallRemoveService", "http", "trusted", False)
        mock_run.assert_not_called()

    @patch('services.security.firewall.subprocess.run')
    @patch('services.security.firewall.daemon_client.call_json')
    def test_add_rich_rule_prefers_daemon(self, mock_call_json, mock_run):
        rule = 'rule family="ipv4" accept'
        mock_call_json.return_value = {"success": True, "message": "added"}
        result = FirewallManager.add_rich_rule(
            rule, zone="public", permanent=True)
        self.assertTrue(result.success)
        self.assertEqual(result.message, "added")
        mock_call_json.assert_called_once_with(
            "FirewallAddRichRule", rule, "public", True)
        mock_run.assert_not_called()

    @patch('services.security.firewall.subprocess.run')
    @patch('services.security.firewall.daemon_client.call_json')
    def test_remove_rich_rule_prefers_daemon(self, mock_call_json, mock_run):
        rule = 'rule family="ipv4" accept'
        mock_call_json.return_value = {"success": True, "message": "removed"}
        result = FirewallManager.remove_rich_rule(
            rule, zone="public", permanent=True)
        self.assertTrue(result.success)
        self.assertEqual(result.message, "removed")
        mock_call_json.assert_called_once_with(
            "FirewallRemoveRichRule", rule, "public", True)
        mock_run.assert_not_called()

    @patch('services.security.firewall.subprocess.run')
    @patch('services.security.firewall.daemon_client.call_json')
    def test_open_port_prefers_daemon(self, mock_call_json, mock_run):
        mock_call_json.return_value = {"success": True, "message": "opened"}
        result = FirewallManager.open_port("80", "tcp", "public", True)
        self.assertTrue(result.success)
        self.assertEqual(result.message, "opened")
        mock_call_json.assert_called_once_with(
            "FirewallOpenPort", "80", "tcp", "public", True)
        mock_run.assert_not_called()

    @patch('services.security.firewall.subprocess.run')
    @patch('services.security.firewall.daemon_client.call_json')
    def test_close_port_prefers_daemon(self, mock_call_json, mock_run):
        mock_call_json.return_value = {"success": True, "message": "closed"}
        result = FirewallManager.close_port("80", "tcp", "public", True)
        self.assertTrue(result.success)
        self.assertEqual(result.message, "closed")
        mock_call_json.assert_called_once_with(
            "FirewallClosePort", "80", "tcp", "public", True)
        mock_run.assert_not_called()

    @patch('services.security.firewall.subprocess.run')
    @patch('services.security.firewall.daemon_client.call_json')
    def test_start_firewall_prefers_daemon(self, mock_call_json, mock_run):
        mock_call_json.return_value = {"success": True, "message": "started"}
        result = FirewallManager.start_firewall()
        self.assertTrue(result.success)
        self.assertEqual(result.message, "started")
        mock_call_json.assert_called_once_with("FirewallStart")
        mock_run.assert_not_called()

    @patch('services.security.firewall.subprocess.run')
    @patch('services.security.firewall.daemon_client.call_json')
    def test_stop_firewall_prefers_daemon(self, mock_call_json, mock_run):
        mock_call_json.return_value = {"success": True, "message": "stopped"}
        result = FirewallManager.stop_firewall()
        self.assertTrue(result.success)
        self.assertEqual(result.message, "stopped")
        mock_call_json.assert_called_once_with("FirewallStop")
        mock_run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
