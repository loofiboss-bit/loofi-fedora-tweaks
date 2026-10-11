"""Health results summarize incomplete checks without repeating source lists."""

import unittest

from PyQt6.QtWidgets import QApplication

from core.troubleshooting.models import SourceResult, TroubleshootingSession
from core.troubleshooting.profiles import require_profile
from ui.troubleshoot_widget import TroubleshootWidget


class _History:
    def latest(self):
        return None, ""

    def sessions(self):
        return ()


class TestTroubleshootResultSummary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_incomplete_sources_are_summarized_once_and_details_remain_available(self):
        profile = require_profile("system_slow")
        results = []
        for index, budget in enumerate(profile.source_budgets):
            state = "unavailable" if index == 0 else "empty"
            common = (budget.source_id, state, 10.0, 11.0, budget.timeout_seconds)
            if state == "unavailable":
                results.append(SourceResult(*common, reason_code="source-unavailable", message="Source could not be read."))
            else:
                results.append(SourceResult(*common))
        session = TroubleshootingSession(
            "12345678-1234-5678-9234-567812345678",
            profile.id,
            profile.version,
            "traditional",
            "partial",
            10.0,
            11.0,
            source_results=tuple(results),
        )
        widget = TroubleshootWidget(history=_History())
        self.addCleanup(widget.close)

        widget._render_session(session, None, "")

        self.assertIn("Some checks were incomplete", widget.result_notice.message_label.text())
        self.assertFalse(widget.partial_warning.isVisible())
        details = widget.sources_disclosure.details.toPlainText()
        self.assertIn("Freshness/readiness reason: source-unavailable", details)
        self.assertIn("State: Unavailable", details)


if __name__ == "__main__":
    unittest.main()
