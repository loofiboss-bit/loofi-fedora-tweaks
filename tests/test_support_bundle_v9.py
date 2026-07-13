"""Anchor support bundle compatibility and state status."""

from unittest import TestCase
from unittest.mock import patch

from core.export.support_bundle_v9 import SupportBundleV9


class TestSupportBundleV9(TestCase):
    @patch("core.export.support_bundle_v8.SupportBundleV8.generate_bundle", return_value={"legacy": True})
    @patch("core.state.StateDoctor.run", return_value={"status": "healthy"})
    @patch("core.observability.ObservabilityService.status")
    def test_v9_preserves_legacy_and_adds_integrity(self, status, _doctor, _legacy):
        status.return_value.to_dict.return_value = {"schema_id": "loofi.observability-status"}
        bundle = SupportBundleV9.generate_bundle()
        self.assertTrue(bundle["legacy"])
        self.assertEqual(bundle["support_bundle_version"], 9)
        self.assertEqual(bundle["state_integrity"]["status"], "healthy")
        self.assertFalse(bundle["state_archive_policy"]["private_domains_included"])
