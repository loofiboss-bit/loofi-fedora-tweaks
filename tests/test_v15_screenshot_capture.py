"""Contracts for the v15 canonical screenshot route sequence."""

from __future__ import annotations

import unittest

from core.catalog_models import FedoraVariant
from core.navigation.models import NavigationContext, NavigationDecision, NavigationMode
from core.navigation.policy import NavigationPolicy
from scripts.capture_v8_user_guide_screenshots import ROUTE_SCREENSHOTS


class TestV15ScreenshotCapture(unittest.TestCase):
    def test_capture_routes_are_available_in_the_utility_shell(self):
        standard = NavigationContext(
            mode=NavigationMode.STANDARD,
            installed_components=frozenset({"core", "specialist"}),
            fedora_variant=FedoraVariant.TRADITIONAL,
            capabilities=frozenset({"fedora", "dnf5", "desktop:kde", "session:wayland"}),
        )
        advanced = NavigationContext(
            mode=NavigationMode.ADVANCED,
            installed_components=frozenset({"core", "specialist"}),
            fedora_variant=FedoraVariant.TRADITIONAL,
            capabilities=frozenset({"fedora", "dnf5", "desktop:kde", "session:wayland"}),
        )

        for filename, route_id, requires_advanced in ROUTE_SCREENSHOTS:
            if not route_id:
                continue
            with self.subTest(filename=filename):
                # These four IDs are shell-owned aliases for the v29 landing
                # pages. They deliberately do not revive entries in the
                # compatibility navigation manifest.
                if route_id in {"install", "tune", "fix", "update"}:
                    self.assertFalse(requires_advanced)
                    continue
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
