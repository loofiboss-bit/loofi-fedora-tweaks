"""Software application review-copy, badge, and filter contracts."""

from __future__ import annotations

import unittest

from PyQt6.QtWidgets import QApplication

from ui.software_tab import _ApplicationsSubTab


class TestSoftwareApplicationFilters(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_application_catalogue_is_not_mirrored_locally(self):
        tab = _ApplicationsSubTab()
        self.assertEqual(tab.apps, [])
        self.assertEqual(tab.load_apps(), [])
        self.assertFalse(hasattr(tab, "scroll_layout"))
        self.assertFalse(hasattr(tab, "_source_filter"))
        tab.close()


if __name__ == "__main__":
    unittest.main()
