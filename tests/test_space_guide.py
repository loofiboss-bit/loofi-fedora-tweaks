"""Storage guidance retains partial observations and reviewed navigation."""
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from services.hardware.disk import DiskUsage
from services.storage.reclaim import ReclaimProbeService, _parse_human_size
from services.storage.space_guide import FilesystemObservation, SpaceGuide, SpaceGuideService
from core.workflows import ReclaimAnalysisService
from core.troubleshooting.lifecycle import new_session
from core.troubleshooting.service import DefaultEvidenceCollector


class SpaceGuideTests(unittest.TestCase):
    @patch("services.storage.space_guide.ReclaimProbeService")
    @patch("services.storage.space_guide.DiskManager.get_disk_usage")
    @patch("services.storage.space_guide.os.stat")
    def test_shared_filesystems_grouped_separate_home_preserved(self, stat, disk, reclaim):
        stat.side_effect = [SimpleNamespace(st_dev=1), SimpleNamespace(st_dev=2), SimpleNamespace(st_dev=1)]
        disk.side_effect = [DiskUsage("/", 1000, 800, 200, 80), DiskUsage("/home", 2000, 200, 1800, 10)]
        reclaim.return_value.analyze.return_value = ReclaimAnalysisService.build(atomic=False, package_cache_bytes=10, journal_bytes=20)
        report = SpaceGuideService(clock=lambda: 5).collect()
        self.assertEqual(report.filesystems[0].paths, ("/", "/var"))
        self.assertEqual(report.filesystems[1].paths, ("/home",))
        self.assertEqual(disk.call_count, 2)
        self.assertFalse(report.partial)
        self.assertEqual(report.sampled_at, 5)

    @patch("services.storage.space_guide.ReclaimProbeService")
    @patch("services.storage.space_guide.DiskManager.get_disk_usage", return_value=None)
    @patch("services.storage.space_guide.os.stat", side_effect=PermissionError)
    def test_failed_paths_are_unknown_not_zero(self, _stat, disk, reclaim):
        reclaim.return_value.analyze.return_value = ReclaimAnalysisService.build(atomic=True, package_cache_bytes=None, journal_bytes=None)
        report = SpaceGuideService().collect()
        self.assertTrue(report.partial)
        self.assertTrue(all(row.state == "unknown" and row.free_bytes is None for row in report.filesystems))
        disk.assert_not_called()

    @patch("services.storage.space_guide.ReclaimProbeService")
    @patch("services.storage.space_guide.DiskManager.get_disk_usage", return_value=DiskUsage("/", 0, 0, 0, 0))
    @patch("services.storage.space_guide.os.stat", return_value=SimpleNamespace(st_dev=1))
    def test_invalid_disk_measurement_is_unknown(self, _stat, _disk, reclaim):
        reclaim.return_value.analyze.return_value = ReclaimAnalysisService.build(atomic=False, package_cache_bytes=0, journal_bytes=0)
        self.assertTrue(SpaceGuideService().collect().partial)

    @patch("services.storage.space_guide.SpaceGuideService")
    def test_partial_source_roundtrips_and_never_claims_root_healthy(self, service):
        service.return_value.collect.return_value = SpaceGuide(2, False, (FilesystemObservation(("/",), "unknown"),), None, 20)
        session = new_session("storage_pressure", "traditional", started_at=1)
        result = DefaultEvidenceCollector(clock=lambda: 2)._storage_reclaim(session, 1)
        facts = result.result.facts_dict()
        self.assertEqual(result.result.state, "partial")
        self.assertIsNone(facts["root_usage_percent"])
        self.assertEqual(result.findings, ())
        self.assertEqual(facts["space_guide"]["filesystems"][0]["paths"], "/")

    @patch("services.storage.space_guide.SpaceGuideService")
    def test_pressure_finding_survives_incomplete_cache(self, service):
        service.return_value.collect.return_value = SpaceGuide(2, False, (FilesystemObservation(("/",), "observed", 1000, 960, 40, 96),), None, 20)
        result = DefaultEvidenceCollector(clock=lambda: 2)._storage_reclaim(new_session("storage_pressure", "traditional", started_at=1), 1)
        self.assertEqual(result.result.state, "partial")
        self.assertEqual(result.findings[0].severity, "critical")

    @patch("services.storage.reclaim.os.stat", return_value=SimpleNamespace())
    def test_partial_du_never_becomes_complete_measurement(self, _stat):
        runner = Mock(return_value=subprocess.CompletedProcess([], 1, "123\t/var/cache/dnf\n", "Permission denied"))
        self.assertIsNone(ReclaimProbeService(runner)._package_cache_bytes())

    @patch("services.storage.reclaim.os.stat", return_value=SimpleNamespace())
    def test_complete_cache_requires_each_exact_path_once(self, _stat):
        for output, expected in (("1\t/var/cache/dnf\n2\t/var/cache/libdnf5\n", 3),
                                 ("1\t/var/cache/dnf\n", None),
                                 ("1\t/var/cache/dnf\n1\t/var/cache/dnf\n", None), ("bad", None)):
            with self.subTest(output=output):
                runner = Mock(return_value=subprocess.CompletedProcess([], 0, output, ""))
                self.assertEqual(ReclaimProbeService(runner)._package_cache_bytes(), expected)

    @patch("services.storage.reclaim.os.stat", side_effect=[FileNotFoundError, SimpleNamespace()])
    def test_absent_legacy_cache_does_not_invalidate_dnf5_measurement(self, _stat):
        runner = Mock(return_value=subprocess.CompletedProcess([], 0, "3\t/var/cache/libdnf5\n", ""))
        self.assertEqual(ReclaimProbeService(runner)._package_cache_bytes(), 3)
        runner.assert_called_once_with(["du", "-sb", "/var/cache/libdnf5"], 10)

    @patch("services.storage.reclaim.os.stat", side_effect=PermissionError)
    def test_unreadable_cache_paths_never_count_as_absent(self, _stat):
        runner = Mock()
        self.assertIsNone(ReclaimProbeService(runner)._package_cache_bytes())
        runner.assert_not_called()

    def test_malformed_journal_output_is_unknown(self):
        self.assertIsNone(_parse_human_size("Unexpected error 13"))
        self.assertEqual(_parse_human_size("Archived and active journals take up 4.0M in the file system."), 4194304)


class SpaceGuidePresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_links_only_request_existing_owner_and_keep_scope(self):
        from ui.space_guide import SpaceGuideCard
        card = SpaceGuideCard()
        self.addCleanup(card.close)
        action, route, recheck = Mock(), Mock(), Mock()
        card.actionRequested.connect(action)
        card.routeRequested.connect(route)
        card.recheckRequested.connect(recheck)
        card.set_observation(SpaceGuide(2, False, (FilesystemObservation(("/",), "observed", 100, 95, 5, 95),), 10, 20).to_dict())
        card.cache_button.click()
        action.assert_called_once_with("dnf-clean-all", {})
        card.installation.setCurrentIndex(1)
        card.runtime_button.click()
        route.assert_called_once_with("software:apps", {"section": "unused-runtimes", "installation": "system"})
        card.recheck_button.click()
        recheck.assert_called_once_with()

    def test_atomic_and_unknown_cache_disable_cleanup(self):
        from ui.space_guide import SpaceGuideCard
        card = SpaceGuideCard()
        self.addCleanup(card.close)
        for atomic, cache in ((True, 100), (False, None), (False, 0)):
            card.set_observation(SpaceGuide(2, atomic, (), cache, None).to_dict())
            self.assertFalse(card.cache_button.isEnabled())
        self.assertIn("Unknown", card.observations.text())
