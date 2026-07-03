"""Tests for v12 Support Bundle v8 additions."""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))
sys.path.insert(0, os.path.dirname(__file__))

from core.export.support_bundle_v8 import SupportBundleV8
from test_fedora44_readiness import Fedora44ReadinessReport, _passing_desktop, _passing_package


class TestSupportBundleV8(unittest.TestCase):
    """Support Bundle v8 preserves compatibility and adds timeline fields."""

    @patch.object(SupportBundleV8, "_flatpak_runtimes", return_value="")
    @patch.object(SupportBundleV8, "_recent_journal_warnings", return_value="user@example.com /home/loofi token=abc")
    @patch.object(SupportBundleV8, "_failed_services", return_value=[])
    @patch("core.export.support_bundle_v5.ActionExecutor.get_action_log", return_value=[])
    @patch("core.export.support_bundle_v5.ReportExporter.gather_system_info", return_value={"home": "/home/loofi"})
    @patch("core.export.support_bundle_v5.ReleaseReadiness.run")
    def test_bundle_v8_contains_observability_fields(self, mock_run, _mock_system, _mock_history, _mock_failed, _mock_journal, _mock_flatpak):
        mock_run.return_value = Fedora44ReadinessReport(
            target="Fedora KDE 44",
            generated_at=1.0,
            score=91,
            status="ready",
            summary="ready",
            checks=[],
            desktop=_passing_desktop(),
            package=_passing_package(),
        )

        bundle = SupportBundleV8.generate_bundle()

        self.assertEqual(bundle["schema"], SupportBundleV8.BUNDLE_SCHEMA)
        self.assertEqual(bundle["support_bundle_version"], 8)
        self.assertIn("health_snapshot", bundle)
        self.assertIn("health_timeline", bundle)
        self.assertIn("recurring_problem_fingerprints", bundle)
        self.assertNotIn("/home/loofi", str(bundle))
        self.assertNotIn("user@example.com", str(bundle))


if __name__ == "__main__":
    unittest.main()
