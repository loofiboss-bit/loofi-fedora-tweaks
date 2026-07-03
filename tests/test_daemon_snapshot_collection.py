"""Tests for v12 daemon read-only snapshot collection."""

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))


class TestDaemonSnapshotCollection(unittest.TestCase):
    """Daemon observability methods are read-only and rootless."""

    @patch("core.observability.HealthTimelineStore")
    def test_collect_health_snapshot_envelope(self, mock_store_cls):
        from daemon.server import _collect_health_snapshot

        snapshot = MagicMock()
        snapshot.to_dict.return_value = {"schema_version": 1}
        mock_store_cls.return_value.collect_and_append.return_value = snapshot

        payload = _collect_health_snapshot("44")

        self.assertTrue(payload["read_only"])
        self.assertEqual(payload["snapshot"]["schema_version"], 1)
        mock_store_cls.return_value.collect_and_append.assert_called_once_with(fedora_target="44")

    @patch("daemon.server.dbus", None)
    @patch("core.observability.HealthTimelineStore")
    def test_dbus_method_returns_json_envelope(self, mock_store_cls):
        from daemon.server import DaemonService

        snapshot = MagicMock()
        snapshot.to_dict.return_value = {"schema_version": 1}
        mock_store_cls.return_value.collect_and_append.return_value = snapshot

        envelope = json.loads(DaemonService().ObservabilityCollectHealthSnapshot("44"))

        self.assertTrue(envelope["ok"])
        self.assertTrue(envelope["data"]["read_only"])

    @patch("core.observability.HealthTimelineStore")
    def test_startup_snapshot_failure_is_non_fatal(self, mock_store_cls):
        from daemon.runtime import collect_startup_snapshot

        mock_store_cls.return_value.collect_and_append.side_effect = RuntimeError("missing tool")

        collect_startup_snapshot()

        mock_store_cls.return_value.collect_and_append.assert_called_once_with(fedora_target="44")

    @patch("core.observability.HealthTimelineStore")
    def test_health_timeline_bounds_limit(self, mock_store_cls):
        from daemon.server import _health_timeline

        mock_store_cls.return_value.export.return_value = {"count": 0}

        payload = _health_timeline(999)

        self.assertEqual(payload["count"], 0)
        mock_store_cls.return_value.export.assert_called_once_with(limit=30)

    def test_collect_health_snapshot_rejects_unknown_target(self):
        from daemon.server import _collect_health_snapshot
        from daemon.validators import ValidationError

        with self.assertRaises(ValidationError):
            _collect_health_snapshot("rawhide")

    @patch("daemon.server.dbus", None)
    @patch("core.observability.HealthTimelineStore")
    def test_dbus_method_returns_timeline_json(self, mock_store_cls):
        from daemon.server import DaemonService

        mock_store_cls.return_value.export.return_value = {"count": 2, "snapshots": []}

        envelope = json.loads(DaemonService().ObservabilityHealthTimeline(2))

        self.assertTrue(envelope["ok"])
        self.assertEqual(envelope["data"]["count"], 2)
        mock_store_cls.return_value.export.assert_called_once_with(limit=2)

    @patch("daemon.runtime.LegacyDaemon.run")
    @patch("daemon.runtime.collect_startup_snapshot")
    @patch("daemon.runtime.dbus", None)
    def test_run_daemon_falls_back_without_dbus(self, mock_collect, mock_run):
        from daemon.runtime import run_daemon

        run_daemon()

        mock_collect.assert_called_once_with()
        mock_run.assert_called_once_with()

    @patch("daemon.server.dbus", None)
    @patch("daemon.server.DaemonService._safe_call", return_value='{"ok": true}')
    def test_dbus_wrapper_methods_route_through_safe_call(self, mock_safe_call):
        from daemon.server import DaemonService

        service = DaemonService()
        calls = [
            ("PackageInstall", (["nano"],)),
            ("PackageRemove", (["nano"],)),
            ("PackageUpdate", (["nano"],)),
            ("PackageSearch", ("nano", 5)),
            ("PackageInfo", ("nano",)),
            ("PackageListInstalled", ()),
            ("PackageIsInstalled", ("nano",)),
            ("SystemReboot", ("test", 0)),
            ("SystemShutdown", ("test", 0)),
            ("SystemSuspend", ("test",)),
            ("SystemUpdateGrub", ("test",)),
            ("SystemSetHostname", ("host", "test")),
            ("SystemHasPendingReboot", ()),
            ("SystemGetPackageManager", ()),
            ("SystemGetVariantName", ()),
            ("ServiceListUnits", ("system", "service")),
            ("ServiceStartUnit", ("sshd.service", "system")),
            ("ServiceStopUnit", ("sshd.service", "system")),
            ("ServiceRestartUnit", ("sshd.service", "system")),
            ("ServiceMaskUnit", ("sshd.service", "system")),
            ("ServiceUnmaskUnit", ("sshd.service", "system")),
            ("ServiceGetUnitStatus", ("sshd.service", "system")),
            ("NetworkScanWifi", ()),
            ("NetworkLoadVpnConnections", ()),
            ("NetworkDetectCurrentDns", ()),
            ("NetworkGetActiveConnection", ()),
            ("NetworkCheckHostnamePrivacy", ("home",)),
            ("NetworkReactivateConnection", ("home",)),
            ("NetworkConnectWifi", ("ssid",)),
            ("NetworkDisconnectWifi", ("wlan0",)),
            ("NetworkApplyDns", ("home", "1.1.1.1")),
            ("NetworkSetHostnamePrivacy", ("home", True)),
            ("FirewallGetStatus", ()),
            ("FirewallListPorts", ("public",)),
            ("FirewallListServices", ("public",)),
            ("FirewallGetDefaultZone", ()),
            ("FirewallGetZones", ()),
            ("FirewallGetActiveZones", ()),
            ("FirewallListRichRules", ("public",)),
            ("FirewallSetDefaultZone", ("public",)),
            ("FirewallAddService", ("ssh", "public", True)),
            ("FirewallRemoveService", ("ssh", "public", True)),
            ("FirewallAddRichRule", ("rule", "public", True)),
            ("FirewallRemoveRichRule", ("rule", "public", True)),
            ("FirewallOpenPort", ("22", "tcp", "public", True)),
            ("FirewallClosePort", ("22", "tcp", "public", True)),
            ("FirewallStart", ()),
            ("FirewallStop", ()),
            ("PortAuditScan", ()),
            ("PortAuditSecurityScore", ()),
        ]

        for name, args in calls:
            self.assertEqual(getattr(service, name)(*args), '{"ok": true}')

        self.assertEqual(mock_safe_call.call_count, len(calls))

    @patch("daemon.server.logger")
    def test_safe_call_serializes_validation_and_runtime_errors(self, mock_logger):
        from daemon.server import DaemonService
        from daemon.validators import ValidationError

        validation = json.loads(DaemonService._safe_call(lambda: (_ for _ in ()).throw(ValidationError("bad input"))))
        runtime = json.loads(DaemonService._safe_call(lambda: (_ for _ in ()).throw(RuntimeError("boom"))))

        self.assertFalse(validation["ok"])
        self.assertEqual(validation["error"]["code"], "validation_error")
        self.assertFalse(runtime["ok"])
        self.assertEqual(runtime["error"]["code"], "execution_error")
        mock_logger.exception.assert_called_once_with("Daemon method failure")


if __name__ == "__main__":
    unittest.main()
