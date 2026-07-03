"""Tests for v12 Lighthouse health snapshots."""

import json
import os
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))

from core.diagnostics.daily_maintenance import DailyMaintenanceService
from core.observability import HealthSnapshot
from services.package.dnf5_health import DNF5HealthReport


def _package_report():
    return DNF5HealthReport(
        package_manager="dnf5",
        dnf5_available=True,
        dnf_available=True,
        packagekit_active=True,
        packagekit_detail="active",
        dnf_locked=False,
        lock_detail="No locks",
        repo_probe_ok=True,
        repo_probe_detail="repos ok",
        repo_risks=[],
    )


class _PackageService:
    @staticmethod
    def collect():
        return _package_report()


def _runner(cmd, _timeout):
    stdout_by_command = {
        "flatpak": "flathub\n",
        "systemctl": "bad.service loaded failed failed Example /home/loofi\n",
        "journalctl": "Jul 03 host app[123]: token=abc user@example.com failed with code 42\n",
        "df": "Filesystem Size Used Avail Use% Mounted on\n/dev/root 100G 95G 5G 95% /\n",
    }
    return subprocess.CompletedProcess(cmd, 0, stdout_by_command.get(cmd[0], ""), "")


class TestHealthSnapshot(unittest.TestCase):
    """Snapshot conversion is read-only and privacy-safe."""

    @patch("core.diagnostics.daily_maintenance.shutil.which", return_value="/usr/bin/tool")
    @patch("core.diagnostics.daily_maintenance.SystemManager.is_atomic", return_value=False)
    def test_daily_maintenance_converts_to_privacy_safe_snapshot(self, _mock_atomic, _mock_which):
        report = DailyMaintenanceService(runner=_runner, package_service=_PackageService).collect()
        snapshot = HealthSnapshot.from_daily_maintenance(report, action_center_items=[], fedora_target="44")
        payload = snapshot.to_dict()
        text = json.dumps(payload)

        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["fedora_target"], "44")
        self.assertGreaterEqual(len(payload["problem_fingerprints"]), 2)
        self.assertNotIn("/home/loofi", text)
        self.assertNotIn("user@example.com", text)
        self.assertNotIn("token=abc", text)

    @patch("core.observability.snapshot.SystemManager.is_atomic", return_value=False)
    def test_collect_records_bounded_collection_errors(self, _mock_atomic):
        maintenance_service = MagicMock()
        maintenance_service.collect.side_effect = RuntimeError("maintenance unavailable")
        action_service = MagicMock()
        action_service.candidates_from_readiness.side_effect = ValueError("readiness unavailable")

        snapshot = HealthSnapshot.collect(
            maintenance_service=maintenance_service,
            action_center_service=action_service,
            fedora_target="45-preview",
        )

        self.assertEqual(snapshot.fedora_target, "45-preview")
        self.assertEqual(snapshot.collection_errors, ["maintenance unavailable", "readiness unavailable"])
        self.assertEqual(snapshot.daily_maintenance["recommended_action"], "Collection failed.")

    def test_from_dict_tolerates_malformed_collections(self):
        snapshot = HealthSnapshot.from_dict(
            {
                "daily_maintenance": "bad",
                "action_center_summary": "bad",
                "failed_service_fingerprints": "bad",
                "journal_warning_fingerprints": "bad",
                "disk_usage_summary": "bad",
                "package_manager_health_summary": "bad",
                "rollback_snapshot_availability": "bad",
                "problem_fingerprints": "bad",
                "collection_errors": ["kept", "", None],
            }
        )

        self.assertEqual(snapshot.daily_maintenance, {})
        self.assertEqual(snapshot.failed_service_fingerprints, [])
        self.assertEqual(snapshot.collection_errors, ["kept"])


if __name__ == "__main__":
    unittest.main()
