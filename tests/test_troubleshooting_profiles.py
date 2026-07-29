"""Closed Compass troubleshooting profile and budget contracts."""

from __future__ import annotations

import dataclasses
import unittest

from core.troubleshooting.profiles import all_profiles, require_profile


class TestTroubleshootingProfiles(unittest.TestCase):
    def test_catalog_contains_only_the_six_locked_profiles(self):
        profiles = all_profiles()

        self.assertEqual(
            tuple(profile.id for profile in profiles),
            (
                "system_slow",
                "updates_failed",
                "application_failed",
                "network_problem",
                "storage_pressure",
                "boot_or_deployment",
            ),
        )
        self.assertTrue(all(profile.version == 1 for profile in profiles))

    def test_total_budget_is_exact_for_each_variant(self):
        for profile in all_profiles():
            for variant in ("traditional", "atomic"):
                with self.subTest(profile=profile.id, variant=variant):
                    expected = sum(
                        budget.timeout_seconds
                        for budget in profile.source_budgets
                        if variant in budget.variants
                    )
                    self.assertEqual(profile.total_budget_seconds, expected)

    def test_variant_specific_update_and_boot_sources_do_not_cross(self):
        updates = require_profile("updates_failed")
        boot = require_profile("boot_or_deployment")

        self.assertIsNotNone(updates.budget_for("package-health", "traditional"))
        self.assertIsNone(updates.budget_for("package-health", "atomic"))
        self.assertIsNotNone(updates.budget_for("deployment-state", "atomic"))
        self.assertIsNone(updates.budget_for("deployment-state", "traditional"))
        self.assertIsNotNone(boot.budget_for("package-history", "traditional"))
        self.assertIsNone(boot.budget_for("package-history", "atomic"))
        self.assertIsNotNone(boot.budget_for("deployment-history", "atomic"))

    def test_reduced_profiles_record_the_locked_safety_boundary(self):
        application = require_profile("application_failed")
        network = require_profile("network_problem")

        self.assertEqual(application.availability, "reduced")
        self.assertEqual(
            application.limitation_reason_code,
            "application-journal-collector-unavailable",
        )
        self.assertNotIn(
            "application-journal",
            tuple(item.source_id for item in application.source_budgets),
        )
        self.assertEqual(network.availability, "reduced")
        self.assertEqual(network.limitation_reason_code, "network-scan-excluded")
        self.assertNotIn(
            "network-scan",
            tuple(item.source_id for item in network.source_budgets),
        )

    def test_application_parameter_is_typed_and_other_profiles_reject_parameters(self):
        application = require_profile("application_failed")
        system_slow = require_profile("system_slow")

        parameters = application.validate_parameters(
            {"application_id": "org.kde.kate"}
        )
        self.assertEqual(dict(parameters), {"application_id": "org.kde.kate"})
        for payload in (
            {},
            {"application_id": 5},
            {"application_id": "/home/person/app"},
            {"application_id": "org.kde.kate", "command": "kate"},
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    application.validate_parameters(payload)
        with self.assertRaisesRegex(ValueError, "Unknown"):
            system_slow.validate_parameters({"mode": "fast"})

    def test_profiles_are_immutable_and_unknown_ids_fail_closed(self):
        profile = require_profile("system_slow")

        with self.assertRaises(dataclasses.FrozenInstanceError):
            profile.title = "Changed"
        with self.assertRaisesRegex(ValueError, "Unknown"):
            require_profile("future_profile")


if __name__ == "__main__":
    unittest.main()
