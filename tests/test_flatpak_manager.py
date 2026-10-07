"""
Tests for services/software/flatpak.py — Flatpak Manager.

Covers: get_flatpak_sizes, get_flatpak_permissions, find_orphan_runtimes,
cleanup_unused, get_total_size, _parse_size, is_available.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))

from services.software.flatpak import (
    FlatpakManager,
    FlatpakSizeEntry,
)


class TestFlatpakManagerAvailability(unittest.TestCase):
    """Tests for FlatpakManager.is_available()."""

    @patch("services.software.flatpak.cached_which", return_value="/usr/bin/flatpak")
    def test_flatpak_available(self, mock_which):
        self.assertTrue(FlatpakManager.is_available())

    @patch("services.software.flatpak.cached_which", return_value=None)
    def test_flatpak_not_available(self, mock_which):
        self.assertFalse(FlatpakManager.is_available())


class TestFlatpakSizes(unittest.TestCase):
    """Tests for FlatpakManager.get_flatpak_sizes()."""

    @patch("services.software.flatpak.cached_which", return_value="/usr/bin/flatpak")
    @patch("services.software.flatpak.subprocess.run")
    def test_get_sizes(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "Firefox\torg.mozilla.firefox\t500 MB\torg.freedesktop.Platform\torg.mozilla.firefox/x86_64/stable\n"
                "GIMP\torg.gimp.GIMP\t1.2 GB\torg.gnome.Platform\torg.gimp.GIMP/x86_64/stable\n"
                "Calculator\torg.gnome.Calculator\t10 MB\torg.gnome.Platform\torg.gnome.Calculator/x86_64/stable\n"
            ),
        )
        result = FlatpakManager.get_flatpak_sizes()
        self.assertEqual(len(result), 3)
        # Should be sorted by size descending
        self.assertEqual(result[0].name, "GIMP")
        self.assertGreater(result[0].size_bytes, result[1].size_bytes)

    @patch("services.software.flatpak.cached_which", return_value="/usr/bin/flatpak")
    @patch("services.software.flatpak.subprocess.run")
    def test_get_sizes_empty(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        result = FlatpakManager.get_flatpak_sizes()
        self.assertEqual(len(result), 0)

    @patch("services.software.flatpak.cached_which", return_value=None)
    def test_get_sizes_no_flatpak(self, mock_which):
        result = FlatpakManager.get_flatpak_sizes()
        self.assertEqual(len(result), 0)

    @patch("services.software.flatpak.cached_which", return_value="/usr/bin/flatpak")
    @patch("services.software.flatpak.subprocess.run")
    def test_get_sizes_timeout(self, mock_run, mock_which):
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="flatpak", timeout=30)
        result = FlatpakManager.get_flatpak_sizes()
        self.assertEqual(len(result), 0)


class TestParseSize(unittest.TestCase):
    """Tests for FlatpakManager._parse_size()."""

    def test_parse_gb(self):
        self.assertAlmostEqual(FlatpakManager._parse_size("1.2 GB"), 1.2 * 1024**3, delta=1024)

    def test_parse_mb(self):
        self.assertAlmostEqual(FlatpakManager._parse_size("500 MB"), 500 * 1024**2, delta=1024)

    def test_parse_kb(self):
        self.assertAlmostEqual(FlatpakManager._parse_size("100 kB"), 100 * 1024, delta=1024)

    def test_parse_empty(self):
        self.assertEqual(FlatpakManager._parse_size(""), 0)

    def test_parse_invalid(self):
        self.assertEqual(FlatpakManager._parse_size("unknown"), 0)


class TestFlatpakPermissions(unittest.TestCase):
    """Tests for FlatpakManager.get_flatpak_permissions()."""

    @patch("services.software.flatpak.cached_which", return_value="/usr/bin/flatpak")
    @patch("services.software.flatpak.subprocess.run")
    def test_get_permissions(self, mock_run, mock_which):
        ref = "app/org.mozilla.firefox/x86_64/stable"
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=("[Context]\nshared=network;ipc;\nsockets=x11;wayland;pulseaudio;\nfilesystems=home:ro;/tmp;\n"
                    "[Environment]\nAPI_TOKEN=super-secret-value\n"),
        )
        result = FlatpakManager.get_flatpak_permissions(ref, installation="user", name="Firefox", strict=True)
        self.assertEqual(result.app_id, "org.mozilla.firefox")
        self.assertEqual(result.name, "Firefox")
        self.assertGreater(len(result.permissions), 0)
        self.assertEqual(result.ref, ref)
        self.assertEqual(result.installation, "user")
        self.assertTrue(any(item.key == "filesystems" and item.value == "home:ro" for item in result.permissions))
        self.assertTrue(any(item.key == "filesystems" and item.value == "/tmp" for item in result.permissions))
        self.assertTrue(any(item.key == "sockets" and item.value == "wayland" for item in result.permissions))
        self.assertNotIn("super-secret-value", str(result.to_dict()))
        self.assertEqual(mock_run.call_count, 1)
        self.assertEqual(mock_run.call_args.args[0], ["flatpak", "info", "--user", "--show-permissions", ref])

    @patch("services.software.flatpak.cached_which", return_value=None)
    def test_get_permissions_no_flatpak(self, mock_which):
        result = FlatpakManager.get_flatpak_permissions("app/org.test.App/x86_64/stable", installation="system")
        self.assertEqual(len(result.permissions), 0)
        self.assertTrue(result.error)

    @patch("services.software.flatpak.cached_which", return_value="/usr/bin/flatpak")
    @patch("services.software.flatpak.subprocess.run")
    def test_get_permissions_timeout(self, mock_run, mock_which):
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="flatpak", timeout=15)
        result = FlatpakManager.get_flatpak_permissions("app/org.test.App/x86_64/stable", installation="system")
        self.assertEqual(len(result.permissions), 0)

    @patch("services.software.flatpak.cached_which", return_value="/usr/bin/flatpak")
    @patch("services.software.flatpak.subprocess.run")
    def test_permissions_reject_large_or_failed_response(self, run, _which):
        ref = "app/org.test.App/x86_64/stable"
        run.return_value = MagicMock(returncode=0, stdout="x" * 65537)
        with self.assertRaisesRegex(ValueError, "64 KiB"):
            FlatpakManager.get_flatpak_permissions(ref, installation="work", strict=True)
        run.return_value = MagicMock(returncode=2, stdout="")
        with self.assertRaisesRegex(ValueError, "could not be read"):
            FlatpakManager.get_flatpak_permissions(ref, installation="work", strict=True)


class TestOrphanDetection(unittest.TestCase):
    """Tests for FlatpakManager.find_orphan_runtimes()."""

    @patch("services.software.flatpak_maintenance.FlatpakMaintenanceService")
    def test_find_orphans(self, service):
        service.return_value.unused.return_value = MagicMock(available=True, refs=[
            MagicMock(ref="runtime/org.freedesktop.Platform/x86_64/22.08"), MagicMock(ref="runtime/org.gnome.Platform/x86_64/44")])
        result = FlatpakManager.find_orphan_runtimes()
        self.assertEqual(len(result), 2)

    @patch("services.software.flatpak_maintenance.FlatpakMaintenanceService")
    def test_find_no_orphans(self, service):
        service.return_value.unused.return_value = MagicMock(available=True, refs=[])
        result = FlatpakManager.find_orphan_runtimes()
        self.assertEqual(len(result), 0)

    @patch("services.software.flatpak_maintenance.FlatpakMaintenanceService")
    def test_find_orphans_no_flatpak(self, service):
        service.return_value.unused.return_value = MagicMock(available=False, error="Unavailable")
        self.assertRaises(RuntimeError, FlatpakManager.find_orphan_runtimes)


class TestCleanup(unittest.TestCase):
    """Tests for FlatpakManager.cleanup_unused()."""

    def test_cleanup_command(self):
        self.assertRaises(RuntimeError, FlatpakManager.cleanup_unused)


class TestTotalSize(unittest.TestCase):
    """Tests for FlatpakManager.get_total_size()."""

    @patch("services.software.flatpak.FlatpakManager.get_flatpak_sizes")
    def test_total_size_gb(self, mock_sizes):
        mock_sizes.return_value = [
            FlatpakSizeEntry(name="A", app_id="a", size_bytes=1024**3),
            FlatpakSizeEntry(name="B", app_id="b", size_bytes=1024**3),
        ]
        result = FlatpakManager.get_total_size()
        self.assertIn("GB", result)

    @patch("services.software.flatpak.FlatpakManager.get_flatpak_sizes")
    def test_total_size_mb(self, mock_sizes):
        mock_sizes.return_value = [
            FlatpakSizeEntry(name="A", app_id="a", size_bytes=500 * 1024**2),
        ]
        result = FlatpakManager.get_total_size()
        self.assertIn("MB", result)

    @patch("services.software.flatpak.FlatpakManager.get_flatpak_sizes")
    def test_total_size_empty(self, mock_sizes):
        mock_sizes.return_value = []
        result = FlatpakManager.get_total_size()
        self.assertEqual(result, "0 B")


if __name__ == "__main__":
    unittest.main()
