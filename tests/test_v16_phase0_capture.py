"""Contracts for the v16 Phase 0 screenshot evidence harness."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import capture_v16_phase0 as capture


class TestV16Phase0Capture(unittest.TestCase):
    def test_matrix_has_six_defaults_and_thirteen_viewport_scale_cells(self):
        self.assertEqual(len(capture.DESTINATIONS), 6)
        self.assertEqual(len(capture.VIEWPORT_SCALE_MATRIX), 13)
        self.assertEqual(len(capture.build_capture_matrix()), 78)
        self.assertEqual(
            [(item.destination_id, item.route_id) for item in capture.DESTINATIONS],
            [
                ("home", "atlas_dashboard"),
                ("software_updates", "software:apps"),
                ("system", "system_info"),
                ("network_security", "network"),
                ("desktop", "desktop"),
                ("settings", "settings"),
            ],
        )
        self.assertEqual(
            capture.VIEWPORT_SCALE_MATRIX[-1],
            capture.ViewportScale(2560, 1440, 200),
        )

    def test_matrix_names_are_stable_and_unique(self):
        filenames = [
            capture.capture_filename(destination, viewport)
            for destination, viewport in capture.build_capture_matrix()
        ]
        self.assertEqual(len(filenames), len(set(filenames)))
        self.assertIn("home__860x720__font-100.png", filenames)
        self.assertIn("settings__2560x1440__font-200.png", filenames)

    def test_supplied_reference_bytes_match_contract(self):
        for reference in capture.REFERENCE_SCREENSHOTS:
            with self.subTest(filename=reference.filename):
                source = capture.REFERENCE_SOURCE_DIR / reference.filename
                self.assertTrue(source.is_file())
                self.assertEqual(capture.sha256_file(source), reference.sha256)
                self.assertEqual(
                    capture._image_dimensions(source),
                    (reference.width, reference.height),
                )

    def test_preserved_references_keep_source_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            original_output_root = capture.OUTPUT_ROOT
            capture.OUTPUT_ROOT = output
            try:
                records = capture.preserve_reference_screenshots()
            finally:
                capture.OUTPUT_ROOT = original_output_root

            self.assertEqual(len(records), 2)
            for reference in capture.REFERENCE_SCREENSHOTS:
                target = output / reference.filename
                source = capture.REFERENCE_SOURCE_DIR / reference.filename
                self.assertEqual(target.read_bytes(), source.read_bytes())

    @patch.object(capture, "_git_value", return_value="abc123")
    def test_manifest_records_proxy_limitation_and_raw_storage(self, mock_git_value):
        references = [{"path": "reference.png", "sha256": "abc"}]
        captures = [
            {
                "path": "raw/example.png",
                "sha256": "def",
                "retained": False,
            }
        ]
        sheets = [{"path": "contact-sheets/home.png", "sha256": "ghi"}]
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / "manifest.json"
            original_report_path = capture.REPORT_PATH
            capture.REPORT_PATH = report
            try:
                manifest = capture.write_manifest(references, captures, sheets)
            finally:
                capture.REPORT_PATH = original_report_path

            from_disk = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(from_disk, manifest)
            self.assertEqual(manifest["git_commit"], "abc123")
            mock_git_value.assert_called_once_with("rev-parse", "HEAD")
            self.assertFalse(manifest["capture_policy"]["raw_frames_retained"])
            self.assertIn("proxy", manifest["font_scaling"]["limitation"])
            self.assertIn("Phase 7", manifest["font_scaling"]["limitation"])
            self.assertEqual(manifest["reproduction_command"], capture.REPRODUCTION_COMMAND)

    def test_generated_manifest_matches_matrix_contract(self):
        manifest = json.loads(capture.REPORT_PATH.read_text(encoding="utf-8"))

        self.assertEqual(manifest["git_commit"], "b96eafec85a3d7e55535201dd7459ef5c9de46b1")
        self.assertEqual(len(manifest["captures"]), 78)
        self.assertEqual(len(manifest["contact_sheets"]), 6)
        self.assertEqual(len({entry["sha256"] for entry in manifest["captures"]}), 78)
        self.assertTrue(all(not entry["retained"] for entry in manifest["captures"]))
        self.assertFalse(capture.RAW_DIR.exists())
        for sheet in manifest["contact_sheets"]:
            path = capture.ROOT / sheet["path"]
            self.assertTrue(path.is_file())
            self.assertEqual(capture.sha256_file(path), sheet["sha256"])

    def test_mutation_guard_blocks_privilege_and_mutating_verbs(self):
        rejected = (
            ["pkexec", "dnf", "install", "package"],
            ["dnf", "remove", "package"],
            ["rpm-ostree", "rebase", "fedora:fedora/45/x86_64/kinoite"],
            ["systemctl", "restart", "sshd"],
            ["flatpak", "install", "flathub", "org.example.App"],
        )
        for command in rejected:
            with self.subTest(command=command), self.assertRaises(RuntimeError):
                capture.assert_read_only_command(command)

        capture.assert_read_only_command(["rpm", "-q", "python3"])
        capture.assert_read_only_command(["systemctl", "is-active", "sshd"])


if __name__ == "__main__":
    unittest.main()
