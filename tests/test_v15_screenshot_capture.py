"""Contracts for the v15 canonical screenshot route sequence."""

from __future__ import annotations

import unittest

from core.navigation.models import NavigationContext, NavigationDecision, NavigationMode
from core.navigation.policy import NavigationPolicy
from scripts.capture_v8_user_guide_screenshots import ROUTE_SCREENSHOTS


class TestV15ScreenshotCapture(unittest.TestCase):
    def test_specialist_routes_switch_to_advanced_before_capture(self):
        standard = NavigationContext(
            mode=NavigationMode.STANDARD,
            installed_components=frozenset({"core", "specialist"}),
        )
        advanced = NavigationContext(
            mode=NavigationMode.ADVANCED,
            installed_components=frozenset({"core", "specialist"}),
        )

        for filename, route_id, requires_advanced in ROUTE_SCREENSHOTS:
            if not route_id:
                continue
            with self.subTest(filename=filename):
                selected_context = advanced if requires_advanced else standard
                self.assertEqual(
                    NavigationPolicy.evaluate(route_id, selected_context).decision,
                    NavigationDecision.VISIBLE,
                )
                if requires_advanced:
                    self.assertNotEqual(
                        NavigationPolicy.evaluate(route_id, standard).decision,
                        NavigationDecision.VISIBLE,
                    )


if __name__ == "__main__":
    unittest.main()
