"""Catalog package updates require a distinct explicit RPM transaction review."""
import unittest

from PyQt6.QtWidgets import QApplication

from core.catalog_models import FedoraVariant
from core.tasks.applications import ApplicationContext
from services.software.application_discovery import DiscoverySnapshot
from ui.install_workflow import InstallWorkflowPage


class CatalogPackageReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.page = InstallWorkflowPage(context=ApplicationContext(FedoraVariant.TRADITIONAL, frozenset({"dnf5"})))
        self.addCleanup(self.page.cleanup)
        self.requested = []
        self.page.actionReviewRequested.connect(lambda action, parameters: self.requested.append((action, parameters)))

    def test_catalog_is_never_preselected_or_executed_on_reload(self):
        self.page._apply_discovery(DiscoverySnapshot(refresh_targets=(("fedora", "", ""),)))
        self.assertIsNone(self.page.discovery_refresh_target.currentData())
        self.assertFalse(self.page.discovery_download.isEnabled())
        self.assertEqual(self.requested, [])
        self.assertEqual(self.page.discovery_refresh_target.count(), 5)

    def test_catalog_package_requests_exact_existing_install_action_only(self):
        self.page._apply_discovery(DiscoverySnapshot(refresh_targets=(("fedora", "", ""),)))
        for package in ("appstream-data", "rpmfusion-free-appstream-data", "rpmfusion-nonfree-appstream-data"):
            with self.subTest(package=package):
                before = len(self.requested)
                index = next(index for index in range(self.page.discovery_refresh_target.count())
                             if self.page.discovery_refresh_target.itemData(index) == ("catalog-rpm", "", package))
                self.page.discovery_refresh_target.setCurrentIndex(index)
                self.assertIn("catalog package", self.page.discovery_download.text())
                self.assertEqual(len(self.requested), before)
                self.page.discovery_download.click()
                self.assertEqual(self.requested[-1], ("install-application", {"source": "fedora", "package_id": package}))

    def test_cache_refresh_remains_metadata_only_and_flatpak_only_has_no_rpm_catalogs(self):
        self.page._apply_discovery(DiscoverySnapshot(refresh_targets=(("fedora", "", ""),)))
        self.page.discovery_refresh_target.setCurrentIndex(1)
        self.page.discovery_download.click()
        self.assertEqual(self.requested, [("refresh-application-metadata", {"source": "fedora"})])
        self.page._apply_discovery(DiscoverySnapshot(refresh_targets=(("flatpak", "user", "flathub"),)))
        self.assertEqual(self.page.discovery_refresh_target.count(), 2)

    def test_injected_arbitrary_catalog_package_is_not_handed_to_controller(self):
        self.page.discovery_refresh_target.addItem("Invalid", ("catalog-rpm", "", "arbitrary-package"))
        self.page.discovery_refresh_target.setCurrentIndex(1)
        self.page.discovery_download.click()
        self.assertEqual(self.requested, [])
