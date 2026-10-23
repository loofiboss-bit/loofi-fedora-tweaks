"""Tests for services/network/network.py — NetworkUtils.

Covers:
- Daemon-first IPC calls via daemon_client.call_json
- Fallbacks to local nmcli subprocess executions
- Wifi scan, VPN listing, DNS detection, Active connection lookup
- Hostname privacy checks/settings, Wifi connection/disconnection, DNS configuration
- Failure, timeout, non-zero exit codes, and edge case handling
"""

import os
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add source path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))

from services.network.network import NetworkUtils  # noqa: E402


class TestNetworkUtilsScanWifi(unittest.TestCase):
    """Test WiFi scanning (daemon-first and local fallback)."""

    @patch("services.network.network.daemon_client.call_json")
    def test_scan_wifi_daemon_success(self, mock_daemon):
        """Scan WiFi via daemon returns parsed network tuples."""
        mock_daemon.return_value = [
            {"ssid": "Net1", "signal": "80%", "security": "WPA2", "active": "Connected"},
            {"ssid": "Net2", "signal": "50%", "security": "Open", "active": ""},
            "invalid_non_dict_element",
        ]
        result = NetworkUtils.scan_wifi()
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], ("Net1", "80%", "WPA2", "Connected"))
        self.assertEqual(result[1], ("Net2", "50%", "Open", ""))
        mock_daemon.assert_called_once_with("NetworkScanWifi")

    @patch("services.network.network.subprocess.run")
    @patch("services.network.network.daemon_client.call_json")
    def test_scan_wifi_daemon_fallback_to_local(self, mock_daemon, mock_run):
        """Scan WiFi falls back to local nmcli if daemon returns non-list."""
        mock_daemon.return_value = None
        mock_run.return_value = MagicMock(
            stdout="MyNetwork:85:WPA2:no\nCoffeeShop:70:Open:no\nHome:95::yes\n",
            returncode=0,
        )
        result = NetworkUtils.scan_wifi()
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], ("MyNetwork", "85%", "WPA2", ""))
        self.assertEqual(result[1], ("CoffeeShop", "70%", "Open", ""))
        self.assertEqual(result[2], ("Home", "95%", "Open", "Connected"))

    @patch("services.network.network.subprocess.run")
    def test_scan_wifi_local_hidden_ssid(self, mock_run):
        """Scan WiFi local handles hidden SSID."""
        mock_run.return_value = MagicMock(stdout=":75:WPA2:no\n", returncode=0)
        result = NetworkUtils.scan_wifi_local()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], "(Hidden)")

    @patch("services.network.network.subprocess.run")
    def test_scan_wifi_local_empty_and_blank(self, mock_run):
        """Scan WiFi local returns empty list when output is empty or blank."""
        mock_run.return_value = MagicMock(stdout="\n  \n", returncode=0)
        result = NetworkUtils.scan_wifi_local()
        self.assertEqual(result, [])

    @patch("services.network.network.subprocess.run")
    def test_scan_wifi_local_failure_and_timeout(self, mock_run):
        """Scan WiFi local handles OSError and TimeoutExpired."""
        mock_run.side_effect = OSError("nmcli not found")
        self.assertEqual(NetworkUtils.scan_wifi_local(), [])

        mock_run.side_effect = subprocess.TimeoutExpired("nmcli", 15)
        self.assertEqual(NetworkUtils.scan_wifi_local(), [])


class TestNetworkUtilsVPN(unittest.TestCase):
    """Test VPN connection listing (daemon-first and local fallback)."""

    @patch("services.network.network.daemon_client.call_json")
    def test_load_vpn_connections_daemon_success(self, mock_daemon):
        """Load VPN connections via daemon."""
        mock_daemon.return_value = [
            {"name": "Work VPN", "type": "vpn", "status": "🟢 Active"},
            {"name": "Home VPN", "type": "wireguard", "status": "Inactive"},
            12345,  # non-dict line ignore check
        ]
        result = NetworkUtils.load_vpn_connections()
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], ("Work VPN", "vpn", "🟢 Active"))
        self.assertEqual(result[1], ("Home VPN", "wireguard", "Inactive"))
        mock_daemon.assert_called_once_with("NetworkLoadVpnConnections")

    @patch("services.network.network.subprocess.run")
    @patch("services.network.network.daemon_client.call_json")
    def test_load_vpn_connections_daemon_fallback(self, mock_daemon, mock_run):
        """Load VPN connections falls back to local nmcli."""
        mock_daemon.return_value = None
        mock_run.return_value = MagicMock(
            stdout="Work VPN:vpn:yes\nHome VPN:wireguard:no\nServer:openvpn:yes\nEthernet:ethernet:yes\n",
            returncode=0,
        )
        result = NetworkUtils.load_vpn_connections()
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], ("Work VPN", "vpn", "🟢 Active"))
        self.assertEqual(result[1], ("Home VPN", "wireguard", "Inactive"))
        self.assertEqual(result[2], ("Server", "openvpn", "🟢 Active"))

    @patch("services.network.network.subprocess.run")
    def test_load_vpn_connections_local_failure(self, mock_run):
        """Load VPN connections local returns [] on subprocess error."""
        mock_run.side_effect = subprocess.SubprocessError("Failed")
        self.assertEqual(NetworkUtils.load_vpn_connections_local(), [])


class TestNetworkUtilsDNS(unittest.TestCase):
    """Test DNS detection (daemon-first and local fallback)."""

    @patch("services.network.network.daemon_client.call_json")
    def test_detect_current_dns_daemon_success(self, mock_daemon):
        """Detect current DNS via daemon."""
        mock_daemon.return_value = "1.1.1.1, 8.8.8.8"
        result = NetworkUtils.detect_current_dns()
        self.assertEqual(result, "1.1.1.1, 8.8.8.8")
        mock_daemon.assert_called_once_with("NetworkDetectCurrentDns")

    @patch("services.network.network.subprocess.run")
    @patch("services.network.network.daemon_client.call_json")
    def test_detect_current_dns_daemon_fallback(self, mock_daemon, mock_run):
        """Detect current DNS falls back to local nmcli."""
        mock_daemon.return_value = None
        mock_run.return_value = MagicMock(
            stdout="IP4.DNS[1]:8.8.8.8\nIP4.DNS[2]:8.8.4.4\nIP4.DNS[1]:1.1.1.1\n",
            returncode=0,
        )
        result = NetworkUtils.detect_current_dns()
        self.assertEqual(result, "1.1.1.1, 8.8.4.4, 8.8.8.8")

    @patch("services.network.network.subprocess.run")
    def test_detect_current_dns_local_empty_and_failure(self, mock_run):
        """Detect current DNS local returns empty string when no DNS or error."""
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        self.assertEqual(NetworkUtils.detect_current_dns_local(), "")

        mock_run.side_effect = OSError("nmcli failure")
        self.assertEqual(NetworkUtils.detect_current_dns_local(), "")


class TestNetworkUtilsConnection(unittest.TestCase):
    """Test active connection detection (daemon-first and local fallback)."""

    @patch("services.network.network.daemon_client.call_json")
    def test_get_active_connection_daemon_success(self, mock_daemon):
        """Get active connection via daemon."""
        mock_daemon.return_value = "MyWiFi"
        result = NetworkUtils.get_active_connection()
        self.assertEqual(result, "MyWiFi")
        mock_daemon.assert_called_once_with("NetworkGetActiveConnection")

    @patch("services.network.network.daemon_client.call_json")
    def test_get_active_connection_daemon_empty_str(self, mock_daemon):
        """Get active connection daemon returning empty string yields None."""
        mock_daemon.return_value = ""
        result = NetworkUtils.get_active_connection()
        self.assertIsNone(result)

    @patch("services.network.network.subprocess.run")
    @patch("services.network.network.daemon_client.call_json")
    def test_get_active_connection_daemon_fallback_wifi(self, mock_daemon, mock_run):
        """Get active connection falls back to local WiFi."""
        mock_daemon.return_value = None
        mock_run.return_value = MagicMock(stdout="MyWiFi:wifi\n", returncode=0)
        result = NetworkUtils.get_active_connection()
        self.assertEqual(result, "MyWiFi")

    @patch("services.network.network.subprocess.run")
    def test_get_active_connection_local_ethernet(self, mock_run):
        """Get active connection local ethernet."""
        mock_run.return_value = MagicMock(stdout="Wired con 1:ethernet\n", returncode=0)
        result = NetworkUtils.get_active_connection_local()
        self.assertEqual(result, "Wired con 1")

    @patch("services.network.network.subprocess.run")
    def test_get_active_connection_local_none_and_failure(self, mock_run):
        """Get active connection local returns None on non-matching rows or error."""
        mock_run.return_value = MagicMock(stdout="VPN:vpn\n", returncode=0)
        self.assertIsNone(NetworkUtils.get_active_connection_local())

        mock_run.side_effect = OSError("nmcli failed")
        self.assertIsNone(NetworkUtils.get_active_connection_local())


class TestNetworkUtilsPrivacy(unittest.TestCase):
    """Test hostname privacy checking and updating."""

    @patch("services.network.network.daemon_client.call_json")
    def test_check_hostname_privacy_daemon_success(self, mock_daemon):
        """Check hostname privacy via daemon."""
        mock_daemon.return_value = True
        result = NetworkUtils.check_hostname_privacy("MyConn")
        self.assertTrue(result)
        mock_daemon.assert_called_once_with("NetworkCheckHostnamePrivacy", "MyConn")

    @patch("services.network.network.subprocess.run")
    @patch("services.network.network.daemon_client.call_json")
    def test_check_hostname_privacy_fallback(self, mock_daemon, mock_run):
        """Check hostname privacy falls back to local."""
        mock_daemon.return_value = None
        mock_run.return_value = MagicMock(stdout="ipv4.dhcp-send-hostname:no\n", returncode=0)
        self.assertTrue(NetworkUtils.check_hostname_privacy("MyConn"))

    @patch("services.network.network.subprocess.run")
    def test_check_hostname_privacy_local_visible_and_error(self, mock_run):
        """Check hostname privacy local visible vs failure."""
        mock_run.return_value = MagicMock(stdout="ipv4.dhcp-send-hostname:yes\n", returncode=0)
        self.assertFalse(NetworkUtils.check_hostname_privacy_local("MyConn"))

        mock_run.side_effect = subprocess.SubprocessError("Failed")
        self.assertIsNone(NetworkUtils.check_hostname_privacy_local("MyConn"))

    @patch("services.network.network.daemon_client.call_json")
    def test_set_hostname_privacy_daemon_success(self, mock_daemon):
        """Set hostname privacy via daemon."""
        mock_daemon.return_value = True
        result = NetworkUtils.set_hostname_privacy("MyConn", True)
        self.assertTrue(result)
        mock_daemon.assert_called_once_with("NetworkSetHostnamePrivacy", "MyConn", True)

    @patch("services.network.network.subprocess.run")
    @patch("services.network.network.daemon_client.call_json")
    def test_set_hostname_privacy_fallback_local_hide_true_and_false(self, mock_daemon, mock_run):
        """Set hostname privacy falls back to local nmcli modify."""
        mock_daemon.return_value = None
        mock_run.return_value = MagicMock(returncode=0)

        self.assertTrue(NetworkUtils.set_hostname_privacy("MyConn", hide=True))
        mock_run.assert_called_with(
            ["nmcli", "connection", "modify", "MyConn", "ipv4.dhcp-send-hostname", "no"],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )

        self.assertTrue(NetworkUtils.set_hostname_privacy("MyConn", hide=False))
        mock_run.assert_called_with(
            ["nmcli", "connection", "modify", "MyConn", "ipv4.dhcp-send-hostname", "yes"],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )

    @patch("services.network.network.subprocess.run")
    def test_set_hostname_privacy_local_failure(self, mock_run):
        """Set hostname privacy local handles error and non-zero rc."""
        mock_run.return_value = MagicMock(returncode=1)
        self.assertFalse(NetworkUtils.set_hostname_privacy_local("MyConn", True))

        mock_run.side_effect = OSError("nmcli missing")
        self.assertFalse(NetworkUtils.set_hostname_privacy_local("MyConn", True))


class TestNetworkUtilsConnectionActions(unittest.TestCase):
    """Test connection reactivation, wifi connect, wifi disconnect, and apply DNS."""

    @patch("services.network.network.daemon_client.call_json")
    def test_reactivate_connection_daemon_success(self, mock_daemon):
        """Reactivate connection via daemon."""
        mock_daemon.return_value = True
        result = NetworkUtils.reactivate_connection("MyConn")
        self.assertTrue(result)
        mock_daemon.assert_called_once_with("NetworkReactivateConnection", "MyConn")

    @patch("services.network.network.subprocess.run")
    @patch("services.network.network.daemon_client.call_json")
    def test_reactivate_connection_fallback_local(self, mock_daemon, mock_run):
        """Reactivate connection falls back to local nmcli con up."""
        mock_daemon.return_value = None
        mock_run.return_value = MagicMock(returncode=0)
        self.assertTrue(NetworkUtils.reactivate_connection("MyConn"))
        mock_run.assert_called_once_with(
            ["nmcli", "con", "up", "MyConn"],
            capture_output=True,
            check=False,
            timeout=10,
        )

    @patch("services.network.network.daemon_client.call_json")
    def test_connect_wifi_daemon_success(self, mock_daemon):
        """Connect WiFi via daemon."""
        mock_daemon.return_value = True
        result = NetworkUtils.connect_wifi("MySSID")
        self.assertTrue(result)
        mock_daemon.assert_called_once_with("NetworkConnectWifi", "MySSID")

    @patch("services.network.network.subprocess.run")
    @patch("services.network.network.daemon_client.call_json")
    def test_connect_wifi_fallback_local(self, mock_daemon, mock_run):
        """Connect WiFi falls back to local nmcli."""
        mock_daemon.return_value = None
        mock_run.return_value = MagicMock(returncode=0)
        self.assertTrue(NetworkUtils.connect_wifi("MySSID"))
        mock_run.assert_called_once_with(
            ["nmcli", "device", "wifi", "connect", "MySSID"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )

    @patch("services.network.network.subprocess.run")
    def test_connect_wifi_local_failure(self, mock_run):
        """Connect WiFi local returns False on non-zero return code or exception."""
        mock_run.return_value = MagicMock(returncode=1)
        self.assertFalse(NetworkUtils.connect_wifi_local("MySSID"))

        mock_run.side_effect = subprocess.SubprocessError("Failed")
        self.assertFalse(NetworkUtils.connect_wifi_local("MySSID"))

    @patch("services.network.network.daemon_client.call_json")
    def test_disconnect_wifi_daemon_success(self, mock_daemon):
        """Disconnect WiFi via daemon."""
        mock_daemon.return_value = True
        result = NetworkUtils.disconnect_wifi("wlan0")
        self.assertTrue(result)
        mock_daemon.assert_called_once_with("NetworkDisconnectWifi", "wlan0")

    @patch("services.network.network.subprocess.run")
    @patch("services.network.network.daemon_client.call_json")
    def test_disconnect_wifi_fallback_local(self, mock_daemon, mock_run):
        """Disconnect WiFi falls back to local nmcli with default wlan0."""
        mock_daemon.return_value = None
        mock_run.return_value = MagicMock(returncode=0)
        self.assertTrue(NetworkUtils.disconnect_wifi())
        mock_run.assert_called_once_with(
            ["nmcli", "device", "disconnect", "wlan0"],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )

    @patch("services.network.network.subprocess.run")
    def test_disconnect_wifi_local_failure(self, mock_run):
        """Disconnect WiFi local handles failure."""
        mock_run.side_effect = OSError("Device not found")
        self.assertFalse(NetworkUtils.disconnect_wifi_local("wlan1"))

    @patch("services.network.network.daemon_client.call_json")
    def test_apply_dns_daemon_success(self, mock_daemon):
        """Apply DNS via daemon."""
        mock_daemon.return_value = True
        result = NetworkUtils.apply_dns("Home", "1.1.1.1")
        self.assertTrue(result)
        mock_daemon.assert_called_once_with("NetworkApplyDns", "Home", "1.1.1.1")

    @patch("services.network.network.subprocess.run")
    @patch("services.network.network.daemon_client.call_json")
    def test_apply_dns_fallback_local_auto_and_static(self, mock_daemon, mock_run):
        """Apply DNS falls back to local nmcli for 'auto' and static IP lists."""
        mock_daemon.return_value = None
        mock_run.return_value = MagicMock(returncode=0)

        # Test "auto"
        self.assertTrue(NetworkUtils.apply_dns("Home", "auto"))
        mock_run.assert_called_with(
            [
                "nmcli",
                "con",
                "mod",
                "Home",
                "ipv4.ignore-auto-dns",
                "no",
                "ipv6.ignore-auto-dns",
                "no",
                "ipv4.dns",
                "",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )

        # Test static DNS string
        self.assertTrue(NetworkUtils.apply_dns("Home", "1.1.1.1,8.8.8.8"))
        mock_run.assert_called_with(
            [
                "nmcli",
                "con",
                "mod",
                "Home",
                "ipv4.dns",
                "1.1.1.1,8.8.8.8",
                "ipv4.ignore-auto-dns",
                "yes",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )

    @patch("services.network.network.subprocess.run")
    def test_apply_dns_local_failure(self, mock_run):
        """Apply DNS local returns False on error or non-zero rc."""
        mock_run.return_value = MagicMock(returncode=2)
        self.assertFalse(NetworkUtils.apply_dns_local("Home", "1.1.1.1"))

        mock_run.side_effect = subprocess.SubprocessError("Failed")
        self.assertFalse(NetworkUtils.apply_dns_local("Home", "1.1.1.1"))


if __name__ == "__main__":
    unittest.main()
