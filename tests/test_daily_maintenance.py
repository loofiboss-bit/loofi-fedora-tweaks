"""Tests for v11 Daily Maintenance diagnostics."""

import os
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))

from core.diagnostics.daily_maintenance import DailyMaintenanceService
from services.package.dnf5_health import DNF5HealthReport


def _package_report(locked=False, repo_ok=True):
    return DNF5HealthReport(
        package_manager="dnf5",
        dnf5_available=True,
        dnf_available=True,
        packagekit_active=True,
        packagekit_detail="active",
        dnf_locked=locked,
        lock_detail="locked" if locked else "No locks",
        repo_probe_ok=repo_ok,
        repo_probe_detail="repos ok" if repo_ok else "repo error",
        repo_risks=[],
    )


class _PackageService:
    @staticmethod
    def collect():
        return _package_report()


def _runner(cmd, _timeout):
    stdout_by_command = {
        "flatpak": "flathub\n",
        "systemctl": "",
        "journalctl": "",
        "df": "Filesystem Size Used Avail Use% Mounted on\n/dev/root 100G 40G 60G 40% /\n",
    }
    return subprocess.CompletedProcess(cmd, 0, stdout_by_command.get(cmd[0], ""), "")


class TestDailyMaintenanceService(unittest.TestCase):
    """Daily Maintenance produces deterministic, read-only cards."""

    @patch("core.diagnostics.daily_maintenance.shutil.which", return_value="/usr/bin/tool")
    @patch("core.diagnostics.daily_maintenance.SystemManager.is_atomic", return_value=False)
    def test_traditional_fedora_cards_include_updates_and_recommendation(self, _mock_atomic, _mock_which):
        report = DailyMaintenanceService(runner=_runner, package_service=_PackageService).collect()
        cards = {card.id: card for card in report.cards}

        self.assertFalse(report.atomic)
        self.assertEqual(cards["system-updates"].command_preview, ["dnf5", "check-update"])
        self.assertEqual(cards["package-health"].state, "success")
        self.assertEqual(report.recommended_action, "No immediate maintenance action is required.")

    @patch("core.diagnostics.daily_maintenance.shutil.which", return_value=None)
    @patch("core.diagnostics.daily_maintenance.SystemManager.is_atomic", return_value=True)
    def test_atomic_fedora_uses_rpm_ostree_update_guidance(self, _mock_atomic, _mock_which):
        report = DailyMaintenanceService(runner=_runner, package_service=_PackageService).collect()
        cards = {card.id: card for card in report.cards}

        self.assertTrue(report.atomic)
        self.assertEqual(cards["system-updates"].command_preview, ["rpm-ostree", "upgrade", "--check"])
        self.assertEqual(cards["system-updates"].state, "preview_only")
        self.assertEqual(cards["rollback"].command_preview, ["rpm-ostree", "status"])


if __name__ == "__main__":
    unittest.main()
