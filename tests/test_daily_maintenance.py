"""Tests for v11 Daily Maintenance diagnostics."""

import os
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))

from core.diagnostics.daily_maintenance import DailyMaintenanceService, root_usage_percent
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


class _UnavailablePackageService:
    @staticmethod
    def collect():
        return DNF5HealthReport(
            package_manager="Unknown",
            dnf5_available=False,
            dnf_available=False,
            packagekit_active=False,
            packagekit_detail="unavailable",
            dnf_locked=False,
            lock_detail="No locks",
            repo_probe_ok=False,
            repo_probe_detail="No DNF-compatible package manager found",
            repo_risks=[],
        )


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
        report = DailyMaintenanceService(runner=_runner, package_service=_UnavailablePackageService).collect()
        cards = {card.id: card for card in report.cards}

        self.assertTrue(report.atomic)
        self.assertEqual(cards["system-updates"].command_preview, ["rpm-ostree", "upgrade", "--check"])
        self.assertEqual(cards["system-updates"].state, "preview_only")
        self.assertEqual(cards["package-health"].state, "success")
        self.assertEqual(cards["package-health"].command_preview, ["rpm-ostree", "status"])
        self.assertNotIn("DNF", cards["package-health"].summary)
        self.assertEqual(cards["rollback"].command_preview, ["rpm-ostree", "status"])

    def test_root_usage_accepts_real_df_output_and_only_the_root_mount(self):
        for percentage in (0, 89, 90, 95, 96, 100):
            with self.subTest(percentage=percentage):
                output = (
                    "Filesystem Size Used Avail Use% Mounted on\n"
                    f"/dev/root 100G 96G 4G {percentage}% /\n"
                    "/dev/other 100G 99G 1G 99% /home\n"
                )
                self.assertEqual(root_usage_percent(output), float(percentage))

    def test_root_usage_rejects_missing_invalid_and_ambiguous_data(self):
        for output in (
            "", "Filesystem Size Used Avail Use% Mounted on", "96% /home",
            "101% /", "1000% /", "-1% /", "9.6% /", "96%junk /",
            "96% /\n90% /", "96% /\ninvalid /", "foo 96% /home\ninvalid /",
        ):
            with self.subTest(output=output):
                self.assertIsNone(root_usage_percent(output))

    def test_read_only_probe_errors_never_become_success(self):
        for method in ("_disk_card", "_journal_card", "_failed_services_card"):
            for result, expected in (
                (None, "probe-unavailable"),
                (subprocess.CompletedProcess([], 1, "96% /", "Permission denied"), "probe-permission-denied"),
                (subprocess.CompletedProcess([], 2, "96% /", "failed"), "probe-failed"),
            ):
                with self.subTest(method=method, reason=expected):
                    runner = Mock(return_value=result)
                    card = getattr(DailyMaintenanceService(runner=runner), method)()
                    self.assertEqual(card.state, "error")
                    self.assertEqual(card.error_reason_code, expected)
                    self.assertEqual(card.details, "")
                    self.assertTrue(card.command_preview)
                    self.assertNotIn("error_reason_code", card.to_dict())

    @patch("core.diagnostics.daily_maintenance.subprocess.run")
    def test_production_probe_preserves_precise_exception_reasons(self, run):
        for method in ("_disk_card", "_journal_card", "_failed_services_card"):
            for error, expected in (
                (subprocess.TimeoutExpired("fixture", 1), "probe-timeout"),
                (PermissionError("fixture"), "probe-permission-denied"),
                (FileNotFoundError("fixture"), "probe-unavailable"),
                (OSError("fixture"), "probe-failed"),
                (subprocess.SubprocessError("fixture"), "probe-failed"),
            ):
                with self.subTest(method=method, reason=expected):
                    run.side_effect = error
                    card = getattr(DailyMaintenanceService(), method)()
                    self.assertEqual(card.state, "error")
                    self.assertEqual(card.error_reason_code, expected)
                    self.assertIn("timeout", run.call_args.kwargs)

    def test_disk_success_requires_parseable_root_data(self):
        for output in ("", "output unavailable", "101% /", "96% /home"):
            with self.subTest(output=output):
                card = DailyMaintenanceService(runner=Mock(return_value=subprocess.CompletedProcess([], 0, output, "")))._disk_card()
                self.assertEqual(card.state, "error")
                self.assertEqual(card.error_reason_code, "probe-invalid-output")

    def test_journal_empty_success_is_distinct_from_query_failure(self):
        for output in ("", "-- No entries --"):
            with self.subTest(output=output):
                card = DailyMaintenanceService(runner=Mock(return_value=subprocess.CompletedProcess([], 0, output, "")))._journal_card()
                self.assertEqual(card.state, "success")
                self.assertEqual(card.error_reason_code, "")

    def test_failed_services_rejects_malformed_success_output(self):
        for output in ("unexpected output", "No units available", "garbage 96% /"):
            with self.subTest(output=output):
                card = DailyMaintenanceService(runner=Mock(return_value=subprocess.CompletedProcess([], 0, output, "")))._failed_services_card()
                self.assertEqual(card.state, "error")
                self.assertEqual(card.error_reason_code, "probe-invalid-output")

    def test_service_and_journal_success_retain_actual_warnings(self):
        for method, output in (
            ("_failed_services_card", "demo.service loaded failed failed Demo"),
            ("_journal_card", "Sep 01 host demo: warning"),
        ):
            with self.subTest(method=method):
                card = getattr(DailyMaintenanceService(runner=Mock(return_value=subprocess.CompletedProcess([], 0, output, ""))), method)()
                self.assertEqual(card.state, "warning")
                self.assertEqual(card.details, output)

    @patch("core.diagnostics.daily_maintenance.shutil.which", return_value="/usr/bin/tool")
    def test_flatpak_probe_exception_is_reported(self, _which):
        card = DailyMaintenanceService(runner=Mock(side_effect=subprocess.TimeoutExpired("flatpak", 10)))._flatpak_card()
        self.assertEqual(card.state, "error")
        self.assertEqual(card.error_reason_code, "probe-timeout")


if __name__ == "__main__":
    unittest.main()
