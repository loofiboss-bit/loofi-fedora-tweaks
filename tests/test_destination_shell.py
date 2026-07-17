"""Phase 3 tests for flat destinations and shared secondary navigation."""

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"),
)

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from core.navigation import (
    NavigationContext,
    NavigationMode,
    NavigationPolicy,
    all_destinations,
    destinations_for_mode,
    get_destination,
)
from ui.navigation.destination_host import DestinationHost
from ui.navigation.destination_sidebar import DestinationSidebar


class _QtTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])


class TestDestinationSidebar(_QtTestCase):
    def setUp(self):
        self.sidebar = DestinationSidebar()

    def tearDown(self):
        self.sidebar.close()

    def test_standard_mode_is_exactly_six_flat_rows(self):
        self.sidebar.set_destinations(
            destinations_for_mode(NavigationMode.STANDARD)
        )

        self.assertEqual(
            self.sidebar.destination_ids(),
            (
                "home",
                "software_updates",
                "system",
                "network_security",
                "desktop",
                "settings",
            ),
        )
        self.assertTrue(
            all(
                self.sidebar.topLevelItem(index).childCount() == 0
                for index in range(self.sidebar.topLevelItemCount())
            )
        )

    def test_advanced_mode_adds_only_advanced_destination(self):
        self.sidebar.set_destinations(
            destinations_for_mode(NavigationMode.ADVANCED)
        )

        self.assertEqual(self.sidebar.topLevelItemCount(), 7)
        self.assertEqual(self.sidebar.destination_ids()[-1], "advanced")

    def test_collapsed_mode_keeps_tooltips_and_selection(self):
        self.sidebar.set_destinations(all_destinations())
        self.assertTrue(self.sidebar.select_destination("system"))

        self.sidebar.set_collapsed(True)

        self.assertEqual(self.sidebar.current_destination_id(), "system")
        for index in range(self.sidebar.topLevelItemCount()):
            item = self.sidebar.topLevelItem(index)
            self.assertEqual(item.text(0), "")
            self.assertTrue(item.toolTip(0))

    def test_sidebar_has_no_independent_filter_surface(self):
        self.assertFalse(hasattr(DestinationSidebar, "filter_destinations"))

    def test_rows_scale_from_font_metrics(self):
        self.sidebar.set_destinations(
            destinations_for_mode(NavigationMode.STANDARD)
        )

        expected_minimum = max(
            40,
            int(self.sidebar.fontMetrics().height() * 2.35),
        )
        self.assertGreaterEqual(
            self.sidebar.topLevelItem(0).sizeHint(0).height(),
            expected_minimum,
        )

    def test_high_scale_font_increases_row_height(self):
        self.sidebar.set_destinations(
            destinations_for_mode(NavigationMode.STANDARD)
        )
        normal_height = self.sidebar.topLevelItem(0).sizeHint(0).height()
        font = QFont(self.sidebar.font())
        font.setPointSizeF(max(18.0, font.pointSizeF() * 2.0))
        self.sidebar.setFont(font)

        self.sidebar.set_destinations(
            destinations_for_mode(NavigationMode.STANDARD)
        )

        self.assertGreater(
            self.sidebar.topLevelItem(0).sizeHint(0).height(),
            normal_height,
        )


class TestDestinationHost(_QtTestCase):
    def setUp(self):
        self.host = DestinationHost()
        self.standard = NavigationContext(mode=NavigationMode.STANDARD)

    def tearDown(self):
        self.host.close()

    def test_shared_host_deduplicates_sections_and_keeps_action_center(self):
        destination = get_destination("software_updates")

        self.host.set_destination(destination, self.standard)

        route_ids = self.host.route_ids()
        self.assertIn("software:apps", route_ids)
        self.assertIn("maintenance:action-center", route_ids)
        self.assertNotIn("maintenance:smart-updates", route_ids)
        self.assertEqual(len(route_ids), len(set(route_ids)))

    def test_advanced_host_exposes_advanced_destination_sections(self):
        destination = get_destination("advanced")
        context = NavigationContext(mode=NavigationMode.ADVANCED)

        self.host.set_destination(destination, context)

        self.assertIn("performance", self.host.route_ids())
        self.assertIn("development", self.host.route_ids())
        self.assertGreater(len(self.host.route_ids()), 1)

    def test_active_subroute_selects_owning_section(self):
        destination = get_destination("software_updates")
        self.host.set_destination(destination, self.standard)

        self.host.set_active_route("maintenance:action-center")

        self.assertEqual(
            self.host.tabs.tabData(self.host.tabs.currentIndex()),
            "maintenance:action-center",
        )

    def test_gated_route_has_safe_explanation(self):
        result = NavigationPolicy.evaluate("development", self.standard)

        self.host.show_policy_result(result)

        self.assertTrue(self.host.isVisible())
        self.assertTrue(self.host.explanation.isVisible())
        self.assertIn("Advanced", self.host.explanation.text())

    def test_secondary_navigation_has_narrow_overflow_and_scaled_height(self):
        destination = get_destination("system")
        self.host.resize(360, 100)
        self.host.set_destination(destination, self.standard)

        self.assertTrue(self.host.tabs.usesScrollButtons())
        self.assertFalse(self.host.tabs.expanding())
        self.assertGreaterEqual(
            self.host.tabs.minimumHeight(),
            max(36, int(self.host.fontMetrics().height() * 2.2)),
        )


if __name__ == "__main__":
    unittest.main()
