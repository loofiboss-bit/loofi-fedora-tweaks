"""Software application review-copy, badge, and filter contracts."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication, QFrame, QPushButton

from ui.software_tab import _ApplicationsSubTab


class TestSoftwareApplicationFilters(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    @patch(
        "services.software.applications.SystemManager.is_atomic",
        return_value=False,
    )
    def test_rows_use_review_copy_badges_and_combined_filters(self, _atomic):
        tab = _ApplicationsSubTab()
        tab.apps = [
            {
                "name": "Editor",
                "desc": "Text editor",
                "cmd": "pkexec",
                "args": ["dnf", "install", "-y", "editor"],
                "check_cmd": "rpm -q editor",
            },
            {
                "name": "Example",
                "desc": "Flatpak example",
                "cmd": "flatpak",
                "args": ["install", "-y", "flathub", "org.example.App"],
                "check_cmd": "flatpak info org.example.App",
            },
        ]
        with patch.object(
            tab,
            "check_installed",
            side_effect=lambda command: command == "rpm -q editor",
        ):
            tab.refresh_list()

        rows = [
            tab.scroll_layout.itemAt(index).widget()
            for index in range(tab.scroll_layout.count())
            if isinstance(tab.scroll_layout.itemAt(index).widget(), QFrame)
        ]
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            {
                button.text()
                for row in rows
                for button in row.findChildren(QPushButton)
            },
            {"Review removal", "Review install"},
        )
        for row in rows:
            self.assertIsNotNone(row.findChild(QFrame, "applicationSourceBadge"))
            self.assertIsNotNone(row.findChild(QFrame, "applicationStatusBadge"))

        tab._source_filter.setCurrentIndex(
            tab._source_filter.findData("flatpak")
        )
        self.assertEqual(
            [row.property("appSource") for row in rows if not row.isHidden()],
            ["flatpak"],
        )

        tab._status_filter.setCurrentIndex(
            tab._status_filter.findData("installed")
        )
        self.assertEqual(
            [row for row in rows if not row.isHidden()],
            [],
        )
        tab.close()


if __name__ == "__main__":
    unittest.main()
