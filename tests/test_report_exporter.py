"""Tests for core/export/report_exporter.py"""
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'loofi-fedora-tweaks'))

from core.export.report_exporter import ReportExporter


def _sample_info():
    return {
        "hostname": "test-host",
        "kernel": "6.1.0-test",
        "distro": "Fedora 39",
        "desktop": "KDE",
        "cpu": "Intel i7",
        "gpu": "NVIDIA 3080",
        "ram": "16 GB",
        "disk": "500 GB",
        "uptime": "2 hours",
        "report_date": "2024-01-01",
    }


def _sample_diagnostics():
    return {
        "system_info": _sample_info(),
        "services": [{"unit": "foo.service", "load": "loaded", "active": "failed",
                       "sub": "failed", "description": "Foo Service"}],
        "journal_errors": "Jan 01 00:00:00 test-host kernel: error occurred",
        "updates": "3 packages pending",
        "selinux": {"mode": "Enforcing", "recent_denials": "Jan 01 audit: denied"},
        "network": {"ip_addresses": "192.168.1.1/24", "dns_servers": "8.8.8.8",
                    "default_gateway": "192.168.1.254"},
    }


class TestRunCmd(unittest.TestCase):
    """Tests for ReportExporter._run_cmd helper."""

    @patch('core.export.report_exporter.subprocess.run')
    def test_success_returns_stripped_stdout(self, mock_run):
        # _run_cmd strips stdout
        mock_run.return_value = MagicMock(returncode=0, stdout="ok\n")
        result = ReportExporter._run_cmd(["echo", "ok"])
        self.assertEqual(result, "ok")

    @patch('core.export.report_exporter.subprocess.run')
    def test_nonzero_returns_none(self, mock_run):
        # _run_cmd returns None for non-zero exit code
        mock_run.return_value = MagicMock(returncode=1, stdout="partial\n")
        result = ReportExporter._run_cmd(["cmd"])
        self.assertIsNone(result)

    @patch('core.export.report_exporter.subprocess.run',
           side_effect=subprocess.TimeoutExpired(cmd="x", timeout=5))
    def test_timeout_returns_none(self, _):
        result = ReportExporter._run_cmd(["slow"], timeout=5)
        self.assertIsNone(result)

    @patch('core.export.report_exporter.subprocess.run', side_effect=OSError("no such file"))
    def test_oserror_returns_none(self, _):
        result = ReportExporter._run_cmd(["nonexistent"])
        self.assertIsNone(result)


class TestReadFile(unittest.TestCase):
    """Tests for ReportExporter._read_file helper."""

    def test_reads_and_strips_content(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("  hello world  \n")
            path = f.name
        try:
            result = ReportExporter._read_file(path)
            self.assertEqual(result, "hello world")
        finally:
            os.unlink(path)

    def test_missing_file_returns_none(self):
        result = ReportExporter._read_file("/nonexistent/path/file.txt")
        self.assertIsNone(result)


class TestGatherSystemInfo(unittest.TestCase):
    """Tests for ReportExporter.gather_system_info."""

    @patch('core.export.report_exporter.subprocess.run')
    def test_returns_expected_keys(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="value\n")
        info = ReportExporter.gather_system_info()
        for key in ("hostname", "kernel", "cpu", "ram", "report_date"):
            self.assertIn(key, info)

    @patch('core.export.report_exporter.subprocess.run',
           side_effect=OSError("fail"))
    def test_hostname_fallback_on_error(self, _):
        info = ReportExporter.gather_system_info()
        self.assertIn("hostname", info)
        self.assertIsInstance(info["hostname"], str)


class TestGatherServicesInfo(unittest.TestCase):
    """Tests for ReportExporter.gather_services_info."""

    @patch.object(ReportExporter, '_run_cmd',
                  return_value="foo.service  loaded  failed  failed  Foo\n")
    def test_parses_failed_services(self, _):
        result = ReportExporter.gather_services_info()
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        self.assertIn("unit", result[0])

    @patch.object(ReportExporter, '_run_cmd', return_value=None)
    def test_returns_empty_list_on_none(self, _):
        result = ReportExporter.gather_services_info()
        self.assertEqual(result, [])

    @patch.object(ReportExporter, '_run_cmd', return_value="   \n")
    def test_returns_empty_list_on_blank_output(self, _):
        result = ReportExporter.gather_services_info()
        self.assertEqual(result, [])


class TestGatherJournalErrors(unittest.TestCase):
    """Tests for ReportExporter.gather_journal_errors."""

    @patch.object(ReportExporter, '_run_cmd', return_value="Jan 01 kernel: error")
    def test_returns_output(self, _):
        result = ReportExporter.gather_journal_errors()
        self.assertIn("error", result)

    @patch.object(ReportExporter, '_run_cmd', return_value=None)
    def test_returns_empty_string_on_failure(self, _):
        result = ReportExporter.gather_journal_errors()
        self.assertEqual(result, "")


class TestGatherUpdatesInfo(unittest.TestCase):
    """Tests for ReportExporter.gather_updates_info.

    SystemManager is imported locally inside the function, so we patch it
    at its source module: services.system.system.SystemManager.is_atomic
    """

    @patch('core.export.report_exporter.subprocess.run')
    @patch('services.system.system.SystemManager.is_atomic', return_value=False)
    def test_traditional_pending_updates(self, _, mock_run):
        mock_run.return_value = MagicMock(
            returncode=100,
            stdout="pkg-a  1.0  available\npkg-b  2.0  available\n",
        )
        result = ReportExporter.gather_updates_info()
        self.assertIn("2", result)

    @patch('core.export.report_exporter.subprocess.run')
    @patch('services.system.system.SystemManager.is_atomic', return_value=False)
    def test_traditional_up_to_date(self, _, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        result = ReportExporter.gather_updates_info()
        self.assertIn("up to date", result.lower())

    @patch('core.export.report_exporter.subprocess.run', side_effect=FileNotFoundError)
    @patch('services.system.system.SystemManager.is_atomic', return_value=False)
    def test_dnf_unavailable(self, _, __):
        result = ReportExporter.gather_updates_info()
        self.assertIsInstance(result, str)

    @patch.object(ReportExporter, '_run_cmd', return_value='{"deployments":[]}')
    @patch('services.system.system.SystemManager.is_atomic', return_value=True)
    def test_atomic_returns_string(self, _, __):
        result = ReportExporter.gather_updates_info()
        self.assertIsInstance(result, str)


class TestGatherSelinuxInfo(unittest.TestCase):
    """Tests for ReportExporter.gather_selinux_info."""

    @patch.object(ReportExporter, '_run_cmd', side_effect=["Enforcing", "avc: denied"])
    def test_returns_mode_and_denials(self, _):
        result = ReportExporter.gather_selinux_info()
        self.assertEqual(result["mode"], "Enforcing")
        self.assertIn("denied", result["recent_denials"])

    @patch.object(ReportExporter, '_run_cmd', return_value=None)
    def test_fallback_on_missing_tools(self, _):
        result = ReportExporter.gather_selinux_info()
        self.assertIn("mode", result)
        self.assertIn("recent_denials", result)


class TestGatherNetworkInfo(unittest.TestCase):
    """Tests for ReportExporter.gather_network_info."""

    @patch.object(ReportExporter, '_run_cmd', return_value="inet 192.168.1.1/24 brd")
    @patch.object(ReportExporter, '_read_file', return_value="nameserver 8.8.8.8")
    def test_all_fields_present(self, _, __):
        result = ReportExporter.gather_network_info()
        for key in ("ip_addresses", "dns_servers", "default_gateway"):
            self.assertIn(key, result)

    @patch.object(ReportExporter, '_run_cmd', return_value=None)
    @patch.object(ReportExporter, '_read_file', return_value=None)
    def test_fallback_available(self, _, __):
        result = ReportExporter.gather_network_info()
        for key in ("ip_addresses", "dns_servers", "default_gateway"):
            self.assertIn(key, result)


class TestGatherAllDiagnostics(unittest.TestCase):
    """Tests for ReportExporter.gather_all_diagnostics."""

    @patch.object(ReportExporter, 'gather_system_info', return_value=None)
    @patch.object(ReportExporter, 'gather_services_info', return_value=[])
    @patch.object(ReportExporter, 'gather_journal_errors', return_value="")
    @patch.object(ReportExporter, 'gather_updates_info', return_value="up to date")
    @patch.object(ReportExporter, 'gather_selinux_info',
                  return_value={"mode": "Enforcing", "recent_denials": ""})
    @patch.object(ReportExporter, 'gather_network_info',
                  return_value={"ip_addresses": "", "dns_servers": "", "default_gateway": ""})
    def test_returns_all_six_keys(self, *_):
        result = ReportExporter.gather_all_diagnostics()
        for key in ("system_info", "services", "journal_errors", "updates", "selinux", "network"):
            self.assertIn(key, result)

    @patch.object(ReportExporter, 'gather_system_info',
                  side_effect=RuntimeError("boom"))
    def test_propagates_exception(self, _):
        with self.assertRaises(RuntimeError):
            ReportExporter.gather_all_diagnostics()


class TestExportMarkdown(unittest.TestCase):
    """Tests for ReportExporter.export_markdown."""

    def test_all_six_sections_present(self):
        md = ReportExporter.export_markdown(diagnostics=_sample_diagnostics())
        for heading in (
            "## System Information",
            "## Failed Services",
            "## Recent Journal Errors",
            "## Pending Updates",
            "## SELinux Status",
            "## Network Overview",
        ):
            self.assertIn(heading, md)

    def test_no_failed_services_shows_ok_message(self):
        diag = _sample_diagnostics()
        diag["services"] = []
        md = ReportExporter.export_markdown(diagnostics=diag)
        self.assertIn("No failed services", md)

    def test_legacy_mode_without_diagnostics(self):
        md = ReportExporter.export_markdown(info=_sample_info())
        self.assertIn("# System Report", md)
        self.assertIn("## System Information", md)
        self.assertNotIn("## Failed Services", md)


class TestExportHtml(unittest.TestCase):
    """Tests for ReportExporter.export_html."""

    def test_all_sections_present(self):
        html = ReportExporter.export_html(diagnostics=_sample_diagnostics())
        for section in (
            "System Information",
            "Failed Services",
            "Recent Journal Errors",
            "Pending Updates",
            "SELinux Status",
            "Network Overview",
        ):
            self.assertIn(section, html)

    def test_journal_errors_html_escaped(self):
        diag = _sample_diagnostics()
        diag["journal_errors"] = "<script>alert(1)</script>"
        html = ReportExporter.export_html(diagnostics=diag)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_selinux_denials_html_escaped(self):
        diag = _sample_diagnostics()
        diag["selinux"]["recent_denials"] = "<injection>"
        html = ReportExporter.export_html(diagnostics=diag)
        self.assertNotIn("<injection>", html)

    def test_legacy_mode_without_diagnostics(self):
        html = ReportExporter.export_html(info=_sample_info())
        self.assertIn("<!DOCTYPE html>", html)
        self.assertNotIn("Failed Services", html)


class TestSaveReport(unittest.TestCase):
    """Tests for ReportExporter.save_report."""

    @patch.object(ReportExporter, 'gather_all_diagnostics')
    def test_html_comprehensive(self, mock_gather):
        mock_gather.return_value = _sample_diagnostics()
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        try:
            result = ReportExporter.save_report(path, "html", comprehensive=True)
            self.assertEqual(result, path)
            content = open(path).read()
            self.assertIn("<!DOCTYPE html>", content)
            self.assertIn("Failed Services", content)
        finally:
            os.unlink(path)

    @patch.object(ReportExporter, 'gather_all_diagnostics')
    def test_markdown_comprehensive(self, mock_gather):
        mock_gather.return_value = _sample_diagnostics()
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            path = f.name
        try:
            result = ReportExporter.save_report(path, "markdown", comprehensive=True)
            self.assertEqual(result, path)
            content = open(path).read()
            self.assertIn("# System Report", content)
            self.assertIn("## Failed Services", content)
        finally:
            os.unlink(path)

    @patch.object(ReportExporter, 'gather_system_info')
    def test_legacy_mode(self, mock_gather):
        mock_gather.return_value = _sample_info()
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            path = f.name
        try:
            ReportExporter.save_report(path, "markdown", comprehensive=False)
            content = open(path).read()
            self.assertIn("## System Information", content)
            self.assertNotIn("## Failed Services", content)
        finally:
            os.unlink(path)


if __name__ == '__main__':
    unittest.main()
