"""Tests for release readiness and support bundle compatibility."""

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))

import cli.main as cli_mod
from core.diagnostics.fedora44_readiness import (
    Fedora44Readiness,
    Fedora44ReadinessReport,
    ReadinessCheck,
    ReleaseReadiness,
    TARGETS,
)
from core.export.support_bundle_v3 import SupportBundleV3
from core.export.support_bundle_v4 import SupportBundleV4
from services.desktop.kde44 import KDE44DesktopInfo, KDE44DesktopService
from services.package.dnf5_health import DNF5HealthReport, DNF5HealthService, RepoRisk


def _passing_desktop():
    return KDE44DesktopInfo(
        plasma_version="6.4.0",
        qt_version="6.9.0",
        session_type="wayland",
        desktop="KDE",
        display_manager="SDDM",
        display_manager_active=True,
        display_manager_detail="sddm active",
    )


def _passing_package():
    return DNF5HealthReport(
        package_manager="dnf5",
        dnf5_available=True,
        dnf_available=True,
        packagekit_active=True,
        packagekit_detail="active",
        dnf_locked=False,
        lock_detail="No locks",
        repo_probe_ok=True,
        repo_probe_detail="fedora updates",
        repo_risks=[],
    )


class TestFedoraVersionReadiness(unittest.TestCase):
    """Fedora version parsing is host-independent."""

    def test_fedora44_passes(self):
        check = Fedora44Readiness._fedora_version_check(
            {"VERSION_ID": "44", "PRETTY_NAME": "Fedora Linux 44 (KDE Plasma)"}
        )
        self.assertEqual(check.status, "pass")
        self.assertIn("supported", check.summary)

    def test_fedora43_is_best_effort_warning(self):
        check = Fedora44Readiness._fedora_version_check(
            {"VERSION_ID": "43", "PRETTY_NAME": "Fedora Linux 43 (KDE Plasma)"}
        )
        self.assertEqual(check.status, "warning")
        self.assertIn("best-effort", check.summary)

    def test_unknown_release_errors(self):
        check = Fedora44Readiness._fedora_version_check({})
        self.assertEqual(check.status, "error")

    def test_release_targets_include_fedora45_preview(self):
        target = TARGETS["45-preview"]
        self.assertFalse(target.supported)
        self.assertTrue(target.preview)
        self.assertEqual(target.final_target, "2026-10-20")

    def test_fedora45_preview_accepts_fedora44_context(self):
        check = ReleaseReadiness._fedora_version_check(
            {"VERSION_ID": "44", "PRETTY_NAME": "Fedora Linux 44 (KDE Plasma)"},
            TARGETS["45-preview"],
        )
        self.assertEqual(check.status, "info")
        self.assertIn("preview", check.beginner_guidance.lower())


class TestFedora44ReadinessAggregation(unittest.TestCase):
    """Readiness aggregation uses mocked service state only."""

    def test_qmake_output_prefers_qt_version_line(self):
        output = "QMake version 3.1\nUsing Qt version 6.10.1 in /usr/lib64"
        self.assertEqual(KDE44DesktopService._extract_qt_version(output), "6.10.1")

    @patch.object(Fedora44Readiness, "_tls_check")
    @patch.object(Fedora44Readiness, "_flatpak_check")
    @patch.object(Fedora44Readiness, "_nvidia_check")
    @patch.object(Fedora44Readiness, "_atomic_check")
    @patch("core.diagnostics.fedora44_readiness.DNF5HealthService.collect")
    @patch("core.diagnostics.fedora44_readiness.KDE44DesktopService.collect")
    @patch.object(Fedora44Readiness, "_os_release")
    def test_full_fedora44_report_ready(
        self,
        mock_os_release,
        mock_desktop,
        mock_package,
        mock_atomic,
        mock_nvidia,
        mock_flatpak,
        mock_tls,
    ):
        mock_os_release.return_value = {"VERSION_ID": "44", "PRETTY_NAME": "Fedora Linux 44"}
        mock_desktop.return_value = _passing_desktop()
        mock_package.return_value = _passing_package()
        for mock_check, cid in (
            (mock_atomic, "atomic-status"),
            (mock_nvidia, "nvidia-akmods-secureboot"),
            (mock_flatpak, "flatpak-kde-runtimes"),
            (mock_tls, "tls-cert-compat"),
        ):
            mock_check.return_value = ReadinessCheck(
                id=cid,
                title=cid,
                category="system",
                status="pass",
                severity="info",
                summary="ok",
                beginner_guidance="ok",
            )

        report = Fedora44Readiness.run()
        self.assertEqual(report.status, "ready")
        self.assertGreaterEqual(report.score, 90)
        self.assertTrue(any(check.id == "dnf5-health" for check in report.checks))

    def test_x11_session_is_warning(self):
        desktop = _passing_desktop()
        desktop.session_type = "x11"
        checks = Fedora44Readiness._desktop_checks(desktop)
        session = next(check for check in checks if check.id == "session-type")
        self.assertEqual(session.status, "warning")

    def test_package_risks_warn_for_copr(self):
        package = _passing_package()
        package.repo_risks = [
            RepoRisk(repo_id="copr:<host>:<user>:test", source="/etc/yum.repos.d/copr.repo", risk="warning", reason="COPR")
        ]
        checks = Fedora44Readiness._package_checks(package)
        repos = next(check for check in checks if check.id == "third-party-repos")
        self.assertEqual(repos.status, "warning")
        self.assertIsNotNone(repos.recommendation)

    @patch("core.diagnostics.release_readiness.os.path.exists")
    def test_tls_check_accepts_fedora_ca_bundle_without_legacy_path(self, mock_exists):
        mock_exists.side_effect = lambda path: path == "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem"
        check = ReleaseReadiness._tls_check()
        self.assertEqual(check.status, "info")
        self.assertEqual(check.severity, "info")
        self.assertIn("Fedora CA trust bundle", check.summary)


class TestDNF5HealthService(unittest.TestCase):
    """DNF5 helpers mask private values."""

    def test_repo_text_masking(self):
        masked = DNF5HealthService._mask_repo_text(
            "baseurl=https://example.invalid/?token=secret /home/loofi/file copr:host:loofi:project"
        )
        self.assertIn("token=<masked>", masked)
        self.assertIn("/home/<user>", masked)
        self.assertIn("copr:<host>:<user>:project", masked)


class TestReadinessCLI(unittest.TestCase):
    """CLI command exposes text and JSON readiness output."""

    def setUp(self):
        self._orig_json = cli_mod._json_output

    def tearDown(self):
        cli_mod._json_output = self._orig_json

    @patch("core.diagnostics.release_readiness.ReleaseReadiness.run")
    @patch("cli.main._print")
    def test_cli_text_output(self, mock_print, mock_run):
        cli_mod._json_output = False
        mock_run.return_value = Fedora44ReadinessReport(
            target="Fedora KDE 44",
            generated_at=1.0,
            score=100,
            status="ready",
            summary="ready",
            checks=[
                ReadinessCheck(
                    id="fedora-version",
                    title="Fedora Version",
                    category="system",
                    status="pass",
                    severity="info",
                    summary="Fedora 44",
                    beginner_guidance="ok",
                )
            ],
        )
        result = cli_mod.cmd_fedora44_readiness(MagicMock(advanced=False))
        self.assertEqual(result, 0)
        printed = " ".join(call.args[0] for call in mock_print.call_args_list)
        self.assertIn("Fedora KDE 44 Readiness", printed)

    @patch("core.diagnostics.release_readiness.ReleaseReadiness.run")
    @patch("builtins.print")
    def test_cli_json_output(self, mock_print, mock_run):
        cli_mod._json_output = True
        mock_run.return_value = Fedora44ReadinessReport(
            target="Fedora KDE 44",
            generated_at=1.0,
            score=80,
            status="ready",
            summary="ready",
            checks=[],
        )
        result = cli_mod.cmd_fedora44_readiness(MagicMock(advanced=True))
        self.assertEqual(result, 0)
        payload = json.loads(mock_print.call_args.args[0])
        self.assertEqual(payload["target"], "Fedora KDE 44")

    @patch("core.diagnostics.release_readiness.ReleaseReadiness.run")
    @patch("builtins.print")
    def test_cli_readiness_preview_json_exits_zero(self, mock_print, mock_run):
        cli_mod._json_output = True
        mock_run.return_value = Fedora44ReadinessReport(
            target="Fedora KDE 45 Preview",
            generated_at=1.0,
            score=75,
            status="preview",
            summary="preview",
            checks=[],
            target_metadata=TARGETS["45-preview"],
        )
        result = cli_mod.cmd_readiness(MagicMock(target="45-preview", advanced=True))
        self.assertEqual(result, 0)
        payload = json.loads(mock_print.call_args.args[0])
        self.assertEqual(payload["target_metadata"]["key"], "45-preview")


class TestSupportBundleV3(unittest.TestCase):
    """Support bundle v3 includes masked readiness diagnostics."""

    @patch.object(SupportBundleV4, "_flatpak_runtimes", return_value="org.kde.Platform 6.9 flathub")
    @patch.object(SupportBundleV4, "_recent_journal_warnings", return_value="/home/loofi/token=abc")
    @patch.object(SupportBundleV4, "_failed_services", return_value=[{"unit": "bad.service"}])
    @patch("core.export.support_bundle_v4.ReportExporter.gather_system_info", return_value={"fedora_version": "Fedora 44"})
    @patch("core.export.support_bundle_v4.ReleaseReadiness.run")
    def test_bundle_contains_v3_alias_fields(self, mock_run, _mock_system, _mock_failed, _mock_journal, _mock_flatpak):
        package = _passing_package()
        package.repo_risks = [RepoRisk(repo_id="copr:<host>:<user>:x", source="/etc/yum.repos.d/x.repo", risk="warning", reason="COPR")]
        mock_run.return_value = Fedora44ReadinessReport(
            target="Fedora KDE 44",
            generated_at=1.0,
            score=91,
            status="ready",
            summary="ready",
            checks=[],
            desktop=_passing_desktop(),
            package=package,
        )
        bundle = SupportBundleV3.generate_bundle()
        self.assertEqual(bundle["v"], "6.0.0-compass-support-v4")
        self.assertIn("release_readiness", bundle)
        self.assertIn("fedora_kde_44_readiness", bundle)
        self.assertEqual(bundle["release_readiness"], bundle["fedora_kde_44_readiness"])
        self.assertIn("masked_repo_list", bundle)
        self.assertTrue(bundle["privacy"]["tokens_masked"])


class TestAuroraPackaging(unittest.TestCase):
    """RPM and workflow packaging reflect Fedora 44 and optional runtime split."""

    ROOT = Path(__file__).resolve().parents[1]

    def test_spec_splits_api_and_daemon_dependencies(self):
        spec = (self.ROOT / "loofi-fedora-tweaks.spec").read_text(encoding="utf-8")
        base_section = spec.split("%package api", 1)[0]
        self.assertNotIn("Requires:       python3-fastapi", base_section)
        self.assertNotIn("Requires:       python3-uvicorn", base_section)
        self.assertIn("%package api", spec)
        self.assertIn("%package daemon", spec)
        self.assertIn("Requires:       python3-fastapi", spec)
        self.assertIn("Requires:       python3-dbus", spec)
        self.assertIn("%{_userunitdir}/loofi-fedora-tweaks-api.service", spec)

    def test_workflows_target_fedora44(self):
        for rel_path in (
            ".github/workflows/copr-publish.yml",
            ".github/workflows/auto-release.yml",
        ):
            text = (self.ROOT / rel_path).read_text(encoding="utf-8")
            self.assertNotIn("fedora-43-x86_64", text)
            self.assertNotIn("fedora:43", text)
        copr = (self.ROOT / ".github/workflows/copr-publish.yml").read_text(encoding="utf-8")
        self.assertIn("fedora-44-x86_64", copr)


if __name__ == "__main__":
    unittest.main()
