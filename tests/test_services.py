"""
Tests for utils/services.py — ServiceManager.
Covers: list_units, filter_type, start/stop/restart,
mask/unmask, get_unit_status, gaming detection, failed detection.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add source path to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'loofi-fedora-tweaks'))

from services.system import ServiceManager, ServiceUnit, UnitScope, UnitState

# ---------------------------------------------------------------------------
# TestServiceUnitDataclass — dataclass tests
# ---------------------------------------------------------------------------

class TestServiceUnitDataclass(unittest.TestCase):
    """Tests for ServiceUnit dataclass."""

    def test_service_unit_creation(self):
        """ServiceUnit stores all required fields."""
        unit = ServiceUnit(
            name="gamemoded",
            state=UnitState.ACTIVE,
            scope=UnitScope.USER,
            description="GameMode daemon",
            is_gaming=True,
        )
        self.assertEqual(unit.name, "gamemoded")
        self.assertEqual(unit.state, UnitState.ACTIVE)
        self.assertTrue(unit.is_gaming)

    def test_service_unit_defaults(self):
        """ServiceUnit has correct defaults."""
        unit = ServiceUnit(name="test", state=UnitState.UNKNOWN, scope=UnitScope.SYSTEM)
        self.assertEqual(unit.description, "")
        self.assertFalse(unit.is_gaming)


# ---------------------------------------------------------------------------
# TestDaemonIPC — IPC integration tests
# ---------------------------------------------------------------------------

class TestDaemonIPC(unittest.TestCase):
    """Tests for daemon IPC integration in ServiceManager."""

    @patch('services.system.services.daemon_client.call_json')
    def test_list_units_daemon_success(self, mock_call_json):
        """list_units returns ServiceUnit objects parsed from daemon payload."""
        mock_call_json.return_value = [
            {"name": "gamemoded", "state": "active", "scope": "user", "description": "GameMode", "is_gaming": True},
            {"name": "sshd", "state": "inactive", "scope": "system", "description": "SSH", "is_gaming": False},
            {"name": "failed-service", "state": "failed", "scope": "system"},
            {"name": "activating-service", "state": "activating", "scope": "user"},
            {"name": "deactivating-service", "state": "deactivating", "scope": "user"},
            {"name": "unknown-service", "state": "custom_state", "scope": "user"},
            "invalid_non_dict_row",
        ]

        units = ServiceManager.list_units(UnitScope.USER, "all")

        mock_call_json.assert_called_once_with("ServiceListUnits", "user", "all")
        self.assertEqual(len(units), 6)
        self.assertEqual(units[0].name, "gamemoded")
        self.assertEqual(units[0].state, UnitState.ACTIVE)
        self.assertEqual(units[0].scope, UnitScope.USER)
        self.assertTrue(units[0].is_gaming)

        self.assertEqual(units[1].name, "sshd")
        self.assertEqual(units[1].state, UnitState.INACTIVE)
        self.assertEqual(units[1].scope, UnitScope.SYSTEM)

        self.assertEqual(units[2].state, UnitState.FAILED)
        self.assertEqual(units[3].state, UnitState.ACTIVATING)
        self.assertEqual(units[4].state, UnitState.DEACTIVATING)
        self.assertEqual(units[5].state, UnitState.UNKNOWN)

    @patch('services.system.services.daemon_client.call_json')
    def test_start_unit_daemon(self, mock_call_json):
        """start_unit uses daemon response when returned dict."""
        mock_call_json.return_value = {"success": True, "message": "Started via daemon"}

        result = ServiceManager.start_unit("gamemoded", UnitScope.SYSTEM)

        mock_call_json.assert_called_once_with("ServiceStartUnit", "gamemoded", "system")
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Started via daemon")

    @patch('services.system.services.daemon_client.call_json')
    def test_stop_unit_daemon(self, mock_call_json):
        """stop_unit uses daemon response when returned dict."""
        mock_call_json.return_value = {"success": False, "message": "Failed via daemon"}

        result = ServiceManager.stop_unit("gamemoded", UnitScope.USER)

        mock_call_json.assert_called_once_with("ServiceStopUnit", "gamemoded", "user")
        self.assertFalse(result.success)
        self.assertEqual(result.message, "Failed via daemon")

    @patch('services.system.services.daemon_client.call_json')
    def test_restart_unit_daemon(self, mock_call_json):
        """restart_unit uses daemon response when returned dict."""
        mock_call_json.return_value = {"success": True, "message": "Restarted via daemon"}

        result = ServiceManager.restart_unit("sshd", UnitScope.SYSTEM)

        mock_call_json.assert_called_once_with("ServiceRestartUnit", "sshd", "system")
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Restarted via daemon")

    @patch('services.system.services.daemon_client.call_json')
    def test_mask_unit_daemon(self, mock_call_json):
        """mask_unit uses daemon response when returned dict."""
        mock_call_json.return_value = {"success": True, "message": "Masked via daemon"}

        result = ServiceManager.mask_unit("bluetooth", UnitScope.SYSTEM)

        mock_call_json.assert_called_once_with("ServiceMaskUnit", "bluetooth", "system")
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Masked via daemon")

    @patch('services.system.services.daemon_client.call_json')
    def test_unmask_unit_daemon(self, mock_call_json):
        """unmask_unit uses daemon response when returned dict."""
        mock_call_json.return_value = {"success": True, "message": "Unmasked via daemon"}

        result = ServiceManager.unmask_unit("bluetooth", UnitScope.SYSTEM)

        mock_call_json.assert_called_once_with("ServiceUnmaskUnit", "bluetooth", "system")
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Unmasked via daemon")

    @patch('services.system.services.daemon_client.call_json')
    def test_get_unit_status_daemon(self, mock_call_json):
        """get_unit_status uses daemon string output when available."""
        mock_call_json.return_value = "Active: active (running)"

        status = ServiceManager.get_unit_status("gamemoded", UnitScope.USER)

        mock_call_json.assert_called_once_with("ServiceGetUnitStatus", "gamemoded", "user")
        self.assertEqual(status, "Active: active (running)")

    @patch('services.system.services.subprocess.run')
    @patch('services.system.services.daemon_client.call_json')
    def test_daemon_non_matching_falls_back_to_subprocess(self, mock_call_json, mock_run):
        """ServiceManager falls back to subprocess when daemon returns None or non-matching payload."""
        mock_call_json.return_value = None
        mock_run.return_value = MagicMock(returncode=0, stdout="sshd.service loaded active running OpenSSH\n")

        units = ServiceManager.list_units(UnitScope.USER, "all")

        self.assertEqual(len(units), 1)
        mock_run.assert_called_once()


# ---------------------------------------------------------------------------
# TestListUnits — listing systemd units
# ---------------------------------------------------------------------------

class TestListUnits(unittest.TestCase):
    """Tests for list_units with mocked systemctl output."""

    SAMPLE_OUTPUT = (
        "gamemoded.service        loaded active running GameMode daemon\n"
        "sshd.service             loaded active running OpenSSH server\n"
        "bluetooth.service        loaded failed failed  Bluetooth service\n"
        "tracker-miner.service    loaded inactive dead   Tracker Miner\n"
    )

    @patch('services.system.services.daemon_client.call_json', return_value=None)
    @patch('services.system.services.subprocess.run')
    def test_list_units_parses_output(self, mock_run, _mock_call):
        """list_units parses systemctl output into ServiceUnit list."""
        mock_run.return_value = MagicMock(returncode=0, stdout=self.SAMPLE_OUTPUT)

        units = ServiceManager.list_units(UnitScope.USER, "all")

        self.assertEqual(len(units), 4)
        names = [u.name for u in units]
        self.assertIn("gamemoded", names)

    @patch('services.system.services.daemon_client.call_json', return_value=None)
    @patch('services.system.services.subprocess.run')
    def test_list_units_filter_active(self, mock_run, _mock_call):
        """list_units filters by active state."""
        mock_run.return_value = MagicMock(returncode=0, stdout=self.SAMPLE_OUTPUT)

        units = ServiceManager.list_units(UnitScope.USER, "active")

        for unit in units:
            self.assertEqual(unit.state, UnitState.ACTIVE)

    @patch('services.system.services.daemon_client.call_json', return_value=None)
    @patch('services.system.services.subprocess.run')
    def test_list_units_filter_failed(self, mock_run, _mock_call):
        """list_units filters by failed state."""
        mock_run.return_value = MagicMock(returncode=0, stdout=self.SAMPLE_OUTPUT)

        units = ServiceManager.list_units(UnitScope.USER, "failed")

        self.assertEqual(len(units), 1)
        self.assertEqual(units[0].name, "bluetooth")
        self.assertEqual(units[0].state, UnitState.FAILED)

    @patch('services.system.services.daemon_client.call_json', return_value=None)
    @patch('services.system.services.subprocess.run')
    def test_list_units_filter_gaming(self, mock_run, _mock_call):
        """list_units filters for gaming-related services."""
        mock_run.return_value = MagicMock(returncode=0, stdout=self.SAMPLE_OUTPUT)

        units = ServiceManager.list_units(UnitScope.USER, "gaming")

        self.assertTrue(all(u.is_gaming for u in units))

    @patch('services.system.services.daemon_client.call_json', return_value=None)
    @patch('services.system.services.subprocess.run')
    def test_list_units_parsing_edge_cases(self, mock_run, _mock_call):
        """list_units handles empty lines, short lines, and various states."""
        raw_stdout = (
            "\n"
            "   \n"
            "short.service loaded\n"
            "activating.service loaded activating running Activating Service\n"
            "unknown.service loaded unknown_state running Unknown Service\n"
            "nodesc.service loaded inactive dead\n"
        )
        mock_run.return_value = MagicMock(returncode=0, stdout=raw_stdout)

        units = ServiceManager.list_units(UnitScope.USER, "all")

        self.assertEqual(len(units), 3)
        self.assertEqual(units[0].name, "activating")
        self.assertEqual(units[0].state, UnitState.ACTIVATING)
        self.assertEqual(units[0].description, "Activating Service")

        self.assertEqual(units[1].name, "unknown")
        self.assertEqual(units[1].state, UnitState.UNKNOWN)

        self.assertEqual(units[2].name, "nodesc")
        self.assertEqual(units[2].state, UnitState.INACTIVE)
        self.assertEqual(units[2].description, "")

    @patch('services.system.services.daemon_client.call_json', return_value=None)
    @patch('services.system.services.subprocess.run')
    def test_list_units_nonzero_exit(self, mock_run, _mock_call):
        """list_units returns empty list on error."""
        mock_run.return_value = MagicMock(returncode=1, stdout="")

        units = ServiceManager.list_units()
        self.assertEqual(units, [])

    @patch('services.system.services.daemon_client.call_json', return_value=None)
    @patch('services.system.services.subprocess.run', side_effect=OSError("systemctl not found"))
    def test_list_units_exception(self, mock_run, _mock_call):
        """list_units returns empty list on exception."""
        units = ServiceManager.list_units()
        self.assertEqual(units, [])


# ---------------------------------------------------------------------------
# TestSystemctlCommandConstruction — fallback command verification
# ---------------------------------------------------------------------------

class TestSystemctlCommandConstruction(unittest.TestCase):
    """Tests for exact systemctl fallback command construction."""

    @patch('services.system.services.daemon_client.call_json', return_value=None)
    @patch('services.system.services.subprocess.run')
    def test_start_unit_user_cmd(self, mock_run, _mock_call_json):
        """start_unit constructs correct user command."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        res = ServiceManager.start_unit("gamemoded", UnitScope.USER)

        self.assertTrue(res.success)
        mock_run.assert_called_once_with(
            ["systemctl", "--user", "start", "gamemoded.service"],
            capture_output=True,
            text=True,
            timeout=30,
        )

    @patch('services.system.services.daemon_client.call_json', return_value=None)
    @patch('services.system.services.subprocess.run')
    def test_start_unit_system_cmd(self, mock_run, _mock_call_json):
        """start_unit constructs correct system command using pkexec."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        res = ServiceManager.start_unit("sshd", UnitScope.SYSTEM)

        self.assertTrue(res.success)
        mock_run.assert_called_once_with(
            ["pkexec", "systemctl", "start", "sshd.service"],
            capture_output=True,
            text=True,
            timeout=30,
        )

    @patch('services.system.services.daemon_client.call_json', return_value=None)
    @patch('services.system.services.subprocess.run')
    def test_stop_unit_user_cmd(self, mock_run, _mock_call_json):
        """stop_unit constructs correct user command."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        res = ServiceManager.stop_unit("gamemoded", UnitScope.USER)

        self.assertTrue(res.success)
        mock_run.assert_called_once_with(
            ["systemctl", "--user", "stop", "gamemoded.service"],
            capture_output=True,
            text=True,
            timeout=30,
        )

    @patch('services.system.services.daemon_client.call_json', return_value=None)
    @patch('services.system.services.subprocess.run')
    def test_stop_unit_system_cmd(self, mock_run, _mock_call_json):
        """stop_unit constructs correct system command using pkexec."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        res = ServiceManager.stop_unit("sshd", UnitScope.SYSTEM)

        self.assertTrue(res.success)
        mock_run.assert_called_once_with(
            ["pkexec", "systemctl", "stop", "sshd.service"],
            capture_output=True,
            text=True,
            timeout=30,
        )

    @patch('services.system.services.daemon_client.call_json', return_value=None)
    @patch('services.system.services.subprocess.run')
    def test_restart_unit_user_cmd(self, mock_run, _mock_call_json):
        """restart_unit constructs correct user command."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        res = ServiceManager.restart_unit("gamemoded", UnitScope.USER)

        self.assertTrue(res.success)
        mock_run.assert_called_once_with(
            ["systemctl", "--user", "restart", "gamemoded.service"],
            capture_output=True,
            text=True,
            timeout=30,
        )

    @patch('services.system.services.daemon_client.call_json', return_value=None)
    @patch('services.system.services.subprocess.run')
    def test_restart_unit_system_cmd(self, mock_run, _mock_call_json):
        """restart_unit constructs correct system command using pkexec."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        res = ServiceManager.restart_unit("sshd", UnitScope.SYSTEM)

        self.assertTrue(res.success)
        mock_run.assert_called_once_with(
            ["pkexec", "systemctl", "restart", "sshd.service"],
            capture_output=True,
            text=True,
            timeout=30,
        )

    @patch('services.system.services.daemon_client.call_json', return_value=None)
    @patch('services.system.services.subprocess.run')
    def test_mask_unit_user_cmd(self, mock_run, _mock_call_json):
        """mask_unit constructs correct user command."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        res = ServiceManager.mask_unit("bluetooth", UnitScope.USER)

        self.assertTrue(res.success)
        mock_run.assert_called_once_with(
            ["systemctl", "--user", "mask", "bluetooth.service"],
            capture_output=True,
            text=True,
            timeout=30,
        )

    @patch('services.system.services.daemon_client.call_json', return_value=None)
    @patch('services.system.services.subprocess.run')
    def test_mask_unit_system_cmd(self, mock_run, _mock_call_json):
        """mask_unit constructs correct system command using pkexec."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        res = ServiceManager.mask_unit("bluetooth", UnitScope.SYSTEM)

        self.assertTrue(res.success)
        mock_run.assert_called_once_with(
            ["pkexec", "systemctl", "mask", "bluetooth.service"],
            capture_output=True,
            text=True,
            timeout=30,
        )

    @patch('services.system.services.daemon_client.call_json', return_value=None)
    @patch('services.system.services.subprocess.run')
    def test_unmask_unit_user_cmd(self, mock_run, _mock_call_json):
        """unmask_unit constructs correct user command."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        res = ServiceManager.unmask_unit("bluetooth", UnitScope.USER)

        self.assertTrue(res.success)
        mock_run.assert_called_once_with(
            ["systemctl", "--user", "unmask", "bluetooth.service"],
            capture_output=True,
            text=True,
            timeout=30,
        )

    @patch('services.system.services.daemon_client.call_json', return_value=None)
    @patch('services.system.services.subprocess.run')
    def test_unmask_unit_system_cmd(self, mock_run, _mock_call_json):
        """unmask_unit constructs correct system command using pkexec."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        res = ServiceManager.unmask_unit("bluetooth", UnitScope.SYSTEM)

        self.assertTrue(res.success)
        mock_run.assert_called_once_with(
            ["pkexec", "systemctl", "unmask", "bluetooth.service"],
            capture_output=True,
            text=True,
            timeout=30,
        )

    @patch('services.system.services.daemon_client.call_json', return_value=None)
    @patch('services.system.services.subprocess.run')
    def test_get_unit_status_user_and_system_cmd(self, mock_run, _mock_call_json):
        """get_unit_status constructs correct user and system commands."""
        mock_run.return_value = MagicMock(returncode=0, stdout="Status OK")

        status_user = ServiceManager.get_unit_status("gamemoded", UnitScope.USER)
        self.assertEqual(status_user, "Status OK")
        mock_run.assert_called_with(
            ["systemctl", "--user", "status", "gamemoded.service", "--no-pager"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        status_sys = ServiceManager.get_unit_status("sshd", UnitScope.SYSTEM)
        self.assertEqual(status_sys, "Status OK")
        mock_run.assert_called_with(
            ["systemctl", "status", "sshd.service", "--no-pager"],
            capture_output=True,
            text=True,
            timeout=10,
        )


# ---------------------------------------------------------------------------
# TestStartStopRestart — unit control operations
# ---------------------------------------------------------------------------

class TestStartStopRestart(unittest.TestCase):
    """Tests for start_unit, stop_unit, restart_unit."""

    @patch('services.system.services.daemon_client.call_json', return_value=None)
    @patch('services.system.services.subprocess.run')
    def test_start_unit_success(self, mock_run, _mock_call):
        """start_unit returns success on returncode 0."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        result = ServiceManager.start_unit("gamemoded", UnitScope.USER)
        self.assertTrue(result.success)
        self.assertIn("Started", result.message)

    @patch('services.system.services.daemon_client.call_json', return_value=None)
    @patch('services.system.services.subprocess.run')
    def test_stop_unit_success(self, mock_run, _mock_call):
        """stop_unit returns success on returncode 0."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        result = ServiceManager.stop_unit("gamemoded", UnitScope.USER)
        self.assertTrue(result.success)
        self.assertIn("Stopped", result.message)

    @patch('services.system.services.daemon_client.call_json', return_value=None)
    @patch('services.system.services.subprocess.run')
    def test_restart_unit_success(self, mock_run, _mock_call):
        """restart_unit returns success on returncode 0."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        result = ServiceManager.restart_unit("sshd", UnitScope.SYSTEM)
        self.assertTrue(result.success)
        self.assertIn("Restarted", result.message)

    @patch('services.system.services.daemon_client.call_json', return_value=None)
    @patch('services.system.services.subprocess.run')
    def test_start_unit_failure(self, mock_run, _mock_call):
        """start_unit returns failure on non-zero exit."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="unit not found")

        result = ServiceManager.start_unit("nonexistent")
        self.assertFalse(result.success)
        self.assertIn("Failed to start", result.message)

    @patch('services.system.services.daemon_client.call_json', return_value=None)
    @patch('services.system.services.subprocess.run')
    def test_stop_unit_failure(self, mock_run, _mock_call):
        """stop_unit returns failure on non-zero exit."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="permission denied")

        result = ServiceManager.stop_unit("sshd", UnitScope.SYSTEM)
        self.assertFalse(result.success)
        self.assertIn("Failed to stop", result.message)

    @patch('services.system.services.daemon_client.call_json', return_value=None)
    @patch('services.system.services.subprocess.run')
    def test_restart_unit_failure(self, mock_run, _mock_call):
        """restart_unit returns failure on non-zero exit."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="unit failed")

        result = ServiceManager.restart_unit("sshd", UnitScope.SYSTEM)
        self.assertFalse(result.success)
        self.assertIn("Failed to restart", result.message)

    @patch('services.system.services.daemon_client.call_json', return_value=None)
    @patch('services.system.services.subprocess.run', side_effect=OSError("timeout"))
    def test_action_units_exceptions(self, mock_run, _mock_call):
        """start_unit, stop_unit, restart_unit handle exceptions gracefully."""
        res_start = ServiceManager.start_unit("test")
        self.assertFalse(res_start.success)
        self.assertIn("Error", res_start.message)

        res_stop = ServiceManager.stop_unit("test")
        self.assertFalse(res_stop.success)
        self.assertIn("Error", res_stop.message)

        res_restart = ServiceManager.restart_unit("test")
        self.assertFalse(res_restart.success)
        self.assertIn("Error", res_restart.message)


# ---------------------------------------------------------------------------
# TestMaskUnmask — masking and unmasking units
# ---------------------------------------------------------------------------

class TestMaskUnmask(unittest.TestCase):
    """Tests for mask_unit and unmask_unit."""

    @patch('services.system.services.daemon_client.call_json', return_value=None)
    @patch('services.system.services.subprocess.run')
    def test_mask_unit_success(self, mock_run, _mock_call):
        """mask_unit returns success on returncode 0."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        result = ServiceManager.mask_unit("bluetooth", UnitScope.USER)
        self.assertTrue(result.success)
        self.assertIn("Masked", result.message)

    @patch('services.system.services.daemon_client.call_json', return_value=None)
    @patch('services.system.services.subprocess.run')
    def test_unmask_unit_success(self, mock_run, _mock_call):
        """unmask_unit returns success on returncode 0."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        result = ServiceManager.unmask_unit("bluetooth", UnitScope.USER)
        self.assertTrue(result.success)
        self.assertIn("Unmasked", result.message)

    @patch('services.system.services.daemon_client.call_json', return_value=None)
    @patch('services.system.services.subprocess.run')
    def test_mask_unmask_failures(self, mock_run, _mock_call):
        """mask_unit and unmask_unit return failure on non-zero exit."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="access denied")

        mask_res = ServiceManager.mask_unit("bluetooth", UnitScope.SYSTEM)
        self.assertFalse(mask_res.success)
        self.assertIn("Failed to mask", mask_res.message)

        unmask_res = ServiceManager.unmask_unit("bluetooth", UnitScope.SYSTEM)
        self.assertFalse(unmask_res.success)
        self.assertIn("Failed to unmask", unmask_res.message)

    @patch('services.system.services.daemon_client.call_json', return_value=None)
    @patch('services.system.services.subprocess.run', side_effect=OSError("systemd error"))
    def test_mask_unmask_exceptions(self, mock_run, _mock_call):
        """mask_unit and unmask_unit handle exceptions gracefully."""
        mask_res = ServiceManager.mask_unit("bluetooth")
        self.assertFalse(mask_res.success)
        self.assertIn("Error", mask_res.message)

        unmask_res = ServiceManager.unmask_unit("bluetooth")
        self.assertFalse(unmask_res.success)
        self.assertIn("Error", unmask_res.message)


# ---------------------------------------------------------------------------
# TestGetUnitStatus — detailed status
# ---------------------------------------------------------------------------

class TestGetUnitStatus(unittest.TestCase):
    """Tests for get_unit_status."""

    @patch('services.system.services.subprocess.run')
    def test_get_unit_status_returns_output(self, mock_run):
        """get_unit_status returns systemctl status output."""
        expected = "gamemoded.service - GameMode daemon\n   Active: active (running)\n"
        mock_run.return_value = MagicMock(returncode=0, stdout=expected)

        status = ServiceManager.get_unit_status("gamemoded")
        self.assertIn("active", status)

    @patch('services.system.services.subprocess.run', side_effect=OSError("fail"))
    def test_get_unit_status_handles_exception(self, mock_run):
        """get_unit_status returns empty string on exception."""
        status = ServiceManager.get_unit_status("bad")
        self.assertEqual(status, "")


# ---------------------------------------------------------------------------
# TestGamingAndFailedDetection — convenience methods
# ---------------------------------------------------------------------------

class TestGamingAndFailedDetection(unittest.TestCase):
    """Tests for get_gaming_units and get_failed_units."""

    @patch.object(ServiceManager, 'list_units')
    def test_get_failed_units(self, mock_list):
        """get_failed_units collects from both scopes."""
        mock_list.return_value = [
            ServiceUnit("broken", UnitState.FAILED, UnitScope.USER),
        ]

        ServiceManager.get_failed_units()
        # Called for both USER and SYSTEM scopes
        self.assertEqual(mock_list.call_count, 2)

    @patch.object(ServiceManager, 'list_units')
    def test_get_gaming_units_deduplicates(self, mock_list):
        """get_gaming_units removes duplicates by name."""
        unit = ServiceUnit("gamemoded", UnitState.ACTIVE, UnitScope.USER, is_gaming=True)
        mock_list.return_value = [unit]

        gaming = ServiceManager.get_gaming_units()
        names = [u.name for u in gaming]
        self.assertEqual(names.count("gamemoded"), 1)


if __name__ == '__main__':
    unittest.main()
