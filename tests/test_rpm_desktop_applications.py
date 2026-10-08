"""Desktop-owned RPM discovery preserves partial evidence and package identity."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from core.executor.action_result import ActionResult
from services.software.installed_applications import InstalledApplicationService
from services.software.rpm_desktop_applications import desktop_name, discover_rpm_desktop_applications


class RpmDesktopApplicationsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def entry(self, filename="a.desktop", extra="", name="Uncurated app"):
        path = self.root / filename
        path.write_text(f"[Desktop Entry]\nType=Application\nName={name}\nExec=must-never-run\n{extra}", encoding="utf-8")
        return path

    def discover(self, probe, **kwargs):
        return discover_rpm_desktop_applications(probe, deadline=20, clock=lambda: 0, roots=(self.root,), desktop="KDE", locale="sv_SE.UTF-8", **kwargs)

    def test_visible_localized_app_and_package_deduplication(self):
        a = self.entry(extra="Name[sv]=Svenskt namn\nOnlyShowIn=KDE;\n")
        b = self.entry("b.desktop", name="Second launcher")
        probe = Mock(return_value=ActionResult(True, "read", stdout=f"{a}\tnew-package\n{b}\tnew-package\n"))
        result = self.discover(probe)
        self.assertEqual(result.names, {"new-package": "Svenskt namn"})
        self.assertFalse(result.errors)
        vector, timeout = probe.call_args.args
        self.assertEqual(vector[:5], ("rpm", "-qf", "--qf", "[%{FILENAMES}\\t%{=NAME}\\n]", "--"))
        self.assertEqual(timeout, 8)
        self.assertNotIn("must-never-run", vector)

    def test_hidden_and_desktop_restricted_entries_never_queried(self):
        for index, extra in enumerate(("Hidden=true", "NoDisplay=true", "OnlyShowIn=GNOME;", "NotShowIn=KDE;")):
            self.entry(f"{index}.desktop", extra=extra)
        probe = Mock()
        self.assertFalse(self.discover(probe).names)
        probe.assert_not_called()

    def test_locale_modifier_fallback(self):
        data = "[Desktop Entry]\nType=Application\nName=English\nName[sr@latin]=Latin\n"
        self.assertEqual(desktop_name(data, desktop="KDE", locale="sr_RS.UTF-8@latin"), "Latin")
        self.assertEqual(desktop_name(data, desktop="KDE", locale="sr_RS@latin"), "Latin")

    def test_partial_owner_failure_keeps_verified_associations(self):
        a = self.entry()
        self.entry("unowned.desktop")
        result = self.discover(Mock(return_value=ActionResult(False, "partial", stdout=f"{a}\towned\nfile unowned is not owned\n")))
        self.assertEqual(result.names, {"owned": "Uncurated app"})
        self.assertTrue(result.errors)

    def test_successful_malformed_owner_response_is_partial(self):
        self.entry()
        result = self.discover(Mock(return_value=ActionResult(True, "read", stdout="malformed")))
        self.assertFalse(result.names)
        self.assertTrue(result.errors)

    def test_known_unowned_desktop_file_does_not_make_rpm_source_unknown(self):
        path = self.entry()
        result = self.discover(Mock(return_value=ActionResult(False, "read", exit_code=1, stdout=f"file {path} is not owned by any package\n")))
        self.assertFalse(result.names)
        self.assertFalse(result.errors)

    def test_desktop_string_escapes_are_decoded(self):
        data = r"[Desktop Entry]" + "\nType=Application\nName=Useful\\sapp\\\\name\n"
        self.assertEqual(desktop_name(data, desktop="KDE", locale="C"), "Useful app\\name")

    def test_exhausted_inventory_deadline_skips_rpm_query(self):
        probe = Mock(return_value=ActionResult(True, "flatpaks"))
        clock = Mock(side_effect=[0, 21])
        result = InstalledApplicationService(probe=probe, desktop_roots=(), clock=clock).snapshot()
        self.assertIn("fedora", result.unknown_sources)
        self.assertEqual(probe.call_count, 1)

    def test_malformed_file_is_partial_and_does_not_execute(self):
        self.entry(extra="Name=duplicate\n")
        probe = Mock()
        result = self.discover(probe)
        self.assertTrue(result.errors)
        probe.assert_not_called()

    def test_deadline_prevents_ownership_queries(self):
        self.entry()
        probe = Mock()
        result = discover_rpm_desktop_applications(probe, deadline=0, clock=lambda: 1, roots=(self.root,))
        self.assertTrue(result.errors)
        probe.assert_not_called()

    @patch("services.software.rpm_desktop_applications.BATCH_SIZE", 1)
    def test_multiple_batches_preserve_success_before_failure(self):
        a = self.entry()
        self.entry("b.desktop")
        probe = Mock(side_effect=[ActionResult(True, "read", stdout=f"{a}\tfirst\n"), ActionResult(False, "timeout")])
        result = self.discover(probe)
        self.assertEqual(result.names, {"first": "Uncurated app"})
        self.assertTrue(result.errors)
        self.assertEqual(probe.call_count, 2)

    def test_snapshot_merges_architectures_and_keeps_curated_fallback(self):
        a = self.entry()
        catalog = Mock()
        catalog.all.return_value = [Mock(source="fedora", package_id="curated", name="Curated")]
        probe = Mock(side_effect=[ActionResult(True, "read"),
                                 ActionResult(True, "read", stdout="new-package\t1-1\t10\nnew-package\t1-1\t15\ncurated\t2-1\t12\nother-system-library\t1\t5\n"),
                                 ActionResult(True, "read", stdout=f"{a}\tnew-package\n")])
        result = InstalledApplicationService(probe=probe, catalog=catalog, desktop_roots=(self.root,), clock=lambda: 0).snapshot()
        self.assertFalse(result.errors)
        self.assertEqual([(app.app_id, app.size) for app in result.applications], [("curated", "12 B"), ("new-package", "25 B")])
        self.assertEqual(result.applications[1].name, "Uncurated app")

    def test_partial_discovery_marks_rpm_source_unknown(self):
        self.entry()
        probe = Mock(side_effect=[ActionResult(True, "read"), ActionResult(True, "read", stdout="package\t1\t10\n"), ActionResult(False, "failed")])
        result = InstalledApplicationService(probe=probe, desktop_roots=(self.root,), clock=lambda: 0).snapshot()
        self.assertIn("fedora", result.unknown_sources)


if __name__ == "__main__":
    unittest.main()
