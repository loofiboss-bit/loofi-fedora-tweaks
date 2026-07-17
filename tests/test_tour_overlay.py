"""UI behavior tests for the guided-tour spotlight overlay."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))

from PyQt6.QtWidgets import QApplication, QWidget

from utils.guided_tour import TourStep


app = QApplication.instance() or QApplication(sys.argv)


class TestTourOverlay(unittest.TestCase):
    @staticmethod
    def _steps():
        return [
            TourStep("tourTarget", "Right", "Right-side card", "right"),
            TourStep("tourTarget", "Left", "Left-side card", "left"),
            TourStep("tourTarget", "Above", "Above card", "above"),
            TourStep("tourTarget", "Below", "Below card", "below"),
            TourStep("missingTarget", "Centered", "Centered card", "below"),
        ]

    @patch("ui.tour_overlay.GuidedTourManager.mark_tour_complete")
    @patch("ui.tour_overlay.GuidedTourManager.get_tour_steps")
    def test_full_tour_positions_paints_advances_and_finishes(self, get_steps, mark_complete):
        from ui.tour_overlay import TourOverlay

        get_steps.return_value = self._steps()
        parent = QWidget()
        parent.resize(800, 600)
        target = QWidget(parent)
        target.setObjectName("tourTarget")
        target.setGeometry(100, 120, 180, 80)
        parent.show()
        target.show()
        app.processEvents()

        overlay = TourOverlay(parent)
        completed = MagicMock()
        overlay.tour_completed.connect(completed)
        overlay.start()
        app.processEvents()

        self.assertEqual(overlay.size(), parent.size())
        self.assertTrue(overlay.isVisible())
        self.assertTrue(overlay._target_rect.isValid())
        self.assertEqual(overlay._title_label.text(), "Right")
        self.assertEqual(overlay._step_counter.text(), "Step 1 of 5")

        for index, title in enumerate(("Left", "Above", "Below", "Centered"), start=1):
            overlay._current_step = index
            overlay._update_step()
            self.assertEqual(overlay._title_label.text(), title)
            card_position = overlay._card.pos()
            self.assertGreaterEqual(card_position.x(), 8)
            self.assertGreaterEqual(card_position.y(), 8)

        self.assertFalse(overlay._target_rect.isValid())
        self.assertEqual(overlay._next_btn.text(), "Finish")

        overlay.resize(700, 500)
        overlay.grab()
        app.processEvents()
        overlay._next_step()

        mark_complete.assert_called_once_with()
        self.assertFalse(overlay.isVisible())
        completed.assert_called_once_with()
        parent.close()

    @patch("ui.tour_overlay.GuidedTourManager.mark_tour_complete")
    @patch("ui.tour_overlay.GuidedTourManager.get_tour_steps", return_value=[])
    def test_parentless_empty_tour_and_skip(self, _get_steps, mark_complete):
        from ui.tour_overlay import TourOverlay

        overlay = TourOverlay()
        overlay._position_card(TourStep("none", "None", "None", "below"))
        overlay.start()
        overlay._skip()

        self.assertGreaterEqual(mark_complete.call_count, 2)
        self.assertFalse(overlay.isVisible())


if __name__ == "__main__":
    unittest.main()
