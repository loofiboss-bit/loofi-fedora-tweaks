"""Guide-panel navigation, accessibility labels, and saved-state interaction."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from core.tasks.guides import GUIDE_SCHEMA_ID, GuideProgressStore, GUIDES_BY_ID
from ui.guide_panel import GuidePanel


class TestGuidePanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = GuideProgressStore(Path(self.temp.name) / "guides.json")
        self.panel = GuidePanel(store=self.store)
        self.addCleanup(self.panel.close)

    def tearDown(self):
        self.temp.cleanup()

    def test_open_step_records_in_progress_and_only_emits_navigation_target(self):
        requests = []
        self.panel.targetRequested.connect(requests.append)
        guide = GUIDES_BY_ID["choose-and-manage-apps"]

        self.assertTrue(self.panel.open_guide(guide.id))
        self.panel.step_list.setCurrentRow(1)
        self.panel._open_step()

        saved = self.store.read()
        self.assertEqual(saved.steps[guide.steps[1].id].state, "in_progress")
        self.assertEqual(requests, [guide.steps[1].target])
        self.assertEqual(requests[0].route_id, "install")
        self.assertFalse(hasattr(requests[0], "command"))

    def test_keyboard_can_select_guide_step_and_open_it_without_running_work(self):
        requests = []
        self.panel.targetRequested.connect(requests.append)
        guide = GUIDES_BY_ID["make-fedora-yours"]

        self.panel.show()
        self.app.processEvents()
        self.panel.guide_selector.setFocus()
        QTest.keyClick(self.panel.guide_selector, Qt.Key.Key_Down)
        self.assertEqual(self.panel.active_guide, guide.id)
        self.panel.step_list.setFocus()
        QTest.keyClick(self.panel.step_list, Qt.Key.Key_Down)
        self.assertEqual(self.panel.step_list.currentRow(), 1)
        QTest.keyClick(self.panel.step_list, Qt.Key.Key_Tab)
        self.assertIs(QApplication.focusWidget(), self.panel.open_button)
        QTest.keyClick(self.panel.open_button, Qt.Key.Key_Space)

        self.assertEqual(requests, [guide.steps[1].target])
        self.assertEqual(self.store.read().steps[guide.steps[1].id].state, "in_progress")
        self.assertFalse(hasattr(requests[0], "command"))

    def test_review_skip_and_resume_preserve_distinct_progress(self):
        guide = GUIDES_BY_ID["solve-a-problem"]
        self.panel.open_guide(guide.id)
        self.panel._set_step_state("reviewed")
        self.panel.step_list.setCurrentRow(1)
        self.panel._set_step_state("skipped")
        self.panel.close()

        resumed = GuidePanel(store=self.store)
        self.addCleanup(resumed.close)
        snapshot = self.store.read()
        self.assertEqual(snapshot.active_guide, guide.id)
        self.assertEqual(snapshot.steps[guide.steps[0].id].state, "reviewed")
        self.assertEqual(snapshot.steps[guide.steps[1].id].state, "skipped")
        self.assertEqual(resumed.active_guide, guide.id)
        self.assertIn("Reviewed", resumed.step_list.item(0).text())
        self.assertIn("Skipped", resumed.step_list.item(1).text())

    def test_linked_history_disappearing_is_shown_as_unavailable(self):
        guide = GUIDES_BY_ID["make-fedora-yours"]
        step = guide.steps[2]
        with patch("core.tasks.guides.guide_evidence_exists", return_value=True):
            self.store.update_step(guide.id, step.id, "verified", evidence_kind="action_run", evidence_id="run-exact")
        self.panel.open_guide(guide.id)
        with patch("ui.guide_panel.guide_evidence_exists", return_value=False):
            self.panel._render_steps()
            row = [index for index in range(self.panel.step_list.count()) if self.panel.step_list.item(index).data(Qt.ItemDataRole.UserRole) == step.id][0]
        self.assertIn("Evidence missing", self.panel.step_list.item(row).text())
        self.assertIn("1 unavailable", self.panel.status_label.text())

    def test_reopening_verified_operation_preserves_the_exact_link_and_opens_activity_result(self):
        guide = GUIDES_BY_ID["make-fedora-yours"]
        step = guide.steps[2]
        with patch("core.tasks.guides.guide_evidence_exists", return_value=True):
            self.store.update_step(guide.id, step.id, "verified", evidence_kind="action_run", evidence_id="run-exact")
        targets = []
        self.panel.targetRequested.connect(targets.append)
        self.panel.open_guide(guide.id)
        self.panel.step_list.setCurrentRow(2)
        with patch("ui.guide_panel.guide_evidence_exists", return_value=True):
            self.panel._open_step()

        self.assertEqual(self.store.read().steps[step.id].state, "verified")
        self.assertEqual(self.store.read().steps[step.id].evidence_id, "run-exact")
        self.assertEqual(targets[0].route_id, "changes")
        self.assertEqual(dict(targets[0].context), {"run_id": "run-exact"})

    def test_future_progress_format_remains_untouched_and_panel_is_read_only(self):
        original = json.dumps({"schema_id": GUIDE_SCHEMA_ID, "schema_version": 99, "future": {"keep": True}}).encode()
        self.store.path.write_bytes(original)

        self.assertTrue(self.panel.open_guide("make-fedora-yours"))
        self.assertFalse(self.panel.open_button.isEnabled())
        self.assertIn("newer format", self.panel.status_label.text())
        self.assertEqual(self.store.path.read_bytes(), original)

    def test_corrupt_progress_does_not_break_the_panel_and_is_not_rewritten(self):
        original = b"not-json"
        self.store.path.write_bytes(original)
        self.panel._load_saved_selection()

        self.assertIn("unavailable", self.panel.status_label.text())
        self.assertEqual(self.store.path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
