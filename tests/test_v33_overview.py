"""v33 Overview hierarchy and responsive layout regressions."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
import unittest

from PyQt6.QtWidgets import QApplication

from ui.overview_page import OverviewPage


class TestV33Overview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_resource_panels_precede_details_maintenance_and_guidance(self):
        page = OverviewPage()
        root = page.layout()
        self.assertLess(root.indexOf(page.main_grid), root.indexOf(page.detail_grid))
        self.assertLess(root.indexOf(page.detail_grid), root.indexOf(page.maintenance_card))
        self.assertLess(root.indexOf(page.maintenance_card), root.indexOf(page.intro_card))
        self.assertLess(root.indexOf(page.intro_card), root.indexOf(page.guide_panel))
        page._reflow(1280)
        expected = ("cpu", "memory", "gpu", "storage")
        for index, group in enumerate(expected):
            row, column, _, _ = page.main_grid.getItemPosition(index)
            self.assertEqual((row, column), (0, index))
            self.assertEqual(page.main_grid.itemAt(index).widget(), page._cards[group])
        self.assertEqual(len({id(card) for card, _ in page._maintenance.values()}), 3)
        page.cleanup()

    def test_responsive_columns_and_no_card_overflow(self):
        page = OverviewPage()
        stamp = datetime.now(timezone.utc)
        groups = ("cpu", "memory", "gpu", "storage")
        metrics = tuple(SimpleNamespace(
            id=group, group=group, label=group.upper(), value=35.0, unit="%", status="ready",
            source="fixture", sampled_at=stamp, reason="", detail="", high=None, critical=None,
        ) for group in groups)
        page.set_snapshot(SimpleNamespace(
            identity={}, collected_at=stamp, metrics=metrics, maintenance={}
        ))
        for width, columns in ((900, 2), (1280, 4), (1600, 4)):
            page.resize(width, 800)
            page._reflow(width)
            self.app.processEvents()
            self.assertEqual(page._columns, columns)
            right_edge = page.contentsRect().right()
            for card in page._cards.values():
                if not card.isHidden():
                    self.assertLessEqual(card.geometry().right(), right_edge, f"overflow at width {width}")
            if width == 1280:
                for group in groups:
                    self.assertLessEqual(page._cards[group].geometry().bottom(), 800)
        page.cleanup()

    def test_existing_guide_ids_still_open_from_overview(self):
        from core.tasks.guides import GUIDES

        page = OverviewPage()
        for guide in GUIDES:
            self.assertTrue(page.open_guide(guide.id), guide.id)
        page.cleanup()

    def test_unavailable_resource_values_remain_explicit(self):
        page = OverviewPage()
        stamp = datetime.now(timezone.utc)
        groups = ("cpu", "memory", "gpu", "storage")
        labels = ("CPU usage", "Memory", "GPU", "Storage")
        metrics = tuple(SimpleNamespace(
            id=group, group=group, label=label, value=None, unit="%", status="unavailable",
            source="fixture", sampled_at=stamp, reason="Sensor unavailable", detail="No supported source",
            high=None, critical=None,
        ) for group, label in zip(groups, labels))
        page.set_snapshot(SimpleNamespace(
            identity={"hostname": "Fixture"}, collected_at=stamp, metrics=metrics, maintenance={}
        ))
        for group in groups:
            row = page._rows[group]
            self.assertEqual(row.value.text(), "Unavailable")
            self.assertIn("Sensor unavailable", row.reason.text())
        page.cleanup()

    def test_next_steps_are_limited_to_three(self):
        page = OverviewPage()
        steps = tuple(SimpleNamespace(
            id=f"step-{index}", route="maintenance:updates", context=None,
            title=f"Step {index}", reason="Recorded observation", sampled_at=None,
            button="Review",
        ) for index in range(5))
        page._show_next_steps(steps)
        self.assertEqual(len(page._next_step_rows), 3)
        self.assertEqual(
            [row.layout().itemAt(0).widget().text() for row in page._next_step_rows],
            ["Step 0", "Step 1", "Step 2"],
        )
        page.cleanup()


if __name__ == "__main__":
    unittest.main()
