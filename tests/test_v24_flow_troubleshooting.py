"""V24 guided troubleshooting presentation and inert-selection contracts."""

from __future__ import annotations

import unittest

from PyQt6.QtWidgets import QApplication, QFrame

from ui.components import SectionHeader
from ui.troubleshoot_widget import TroubleshootWidget


class _History:
    def latest(self):
        return None, ""


class TestV24TroubleshootingFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_problem_checks_results_are_explicit_and_initially_inert(self) -> None:
        worker_calls = []
        widget = TroubleshootWidget(
            worker_factory=lambda *args: worker_calls.append(args),
            history=_History(),
        )
        self.addCleanup(widget.deleteLater)

        problem = widget.findChild(QFrame, "troubleshootProfileCard")
        checks = widget.findChild(QFrame, "troubleshootChecksCard")
        self.assertIsNotNone(problem)
        self.assertIsNotNone(checks)
        assert problem is not None and checks is not None
        self.assertEqual(problem.accessibleName(), "1. Problem")
        self.assertEqual(checks.accessibleName(), "2. Checks")
        self.assertIn("3. Results", [header.title_label.text() for header in widget.findChildren(SectionHeader)])
        self.assertEqual(worker_calls, [])

    def test_profile_selection_only_updates_preview(self) -> None:
        worker_calls = []
        widget = TroubleshootWidget(
            worker_factory=lambda *args: worker_calls.append(args),
            history=_History(),
        )
        self.addCleanup(widget.deleteLater)

        widget.profile_selector.setCurrentIndex(widget.profile_selector.findData("storage_full"))

        self.assertEqual(worker_calls, [])
        self.assertIn("Storage and reclaim preview", widget.checks_label.text())
        self.assertFalse(widget.technical_disclosure.toggle_button.isChecked())

    def test_failure_is_explicit_without_replacing_previous_result(self) -> None:
        widget = TroubleshootWidget(history=_History())
        self.addCleanup(widget.deleteLater)
        widget._worker = None

        widget._on_error("collector failed")

        self.assertEqual(widget.start_notice.property("resultKind"), "error")
        self.assertIn("previous completed session", widget.start_notice.message_label.text())


if __name__ == "__main__":
    unittest.main()
