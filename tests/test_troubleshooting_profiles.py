"""Closed Compass troubleshooting profile and budget contracts."""

from __future__ import annotations

import dataclasses
import unittest

from core.troubleshooting.profiles import all_profiles, require_profile
from ui.troubleshoot_presentation import SOURCE_LABELS


class TestTroubleshootingProfiles(unittest.TestCase):
    def test_catalog_contains_the_closed_symptom_profiles(self):
        profiles = all_profiles()

        self.assertEqual(
            tuple(profile.id for profile in profiles),
            (
                "sound_not_working",
                "bluetooth_not_working",
                "screen_sharing_not_working",
                "system_slow",
                "updates_failed",
                "flatpak_updates_failed",
                "firmware_updates_failed",
                "application_failed",
                "network_problem",
                "storage_pressure",
                "boot_or_deployment",
                "battery_problem",
                "display_problem",
                "input_problem",
                "printer_problem",
            ),
        )
        self.assertEqual(require_profile("application_failed").version, 2)
        self.assertEqual(require_profile("network_problem").version, 2)
        self.assertTrue(all(profile.version == 1 for profile in profiles if profile.id not in {"application_failed", "network_problem"}))
        self.assertEqual(require_profile("application_failed", 1).version, 1)
        self.assertEqual(require_profile("network_problem", 1).version, 1)
        self.assertEqual(require_profile("network_problem", 1).required_sources("traditional"),
                         ("network-state", "dns-state"))
        self.assertEqual(require_profile("application_failed", 1).required_sources("traditional"),
                         ("application-inventory", "change-journal"))

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

    def test_application_and_network_profiles_expose_only_local_observations(self):
        application = require_profile("application_failed")
        network = require_profile("network_problem")

        self.assertEqual(application.availability, "available")
        self.assertIn("application-journal", tuple(item.source_id for item in application.source_budgets))
        self.assertIn("network-state", tuple(item.source_id for item in network.source_budgets))
        self.assertNotIn(
            "network-scan",
            tuple(item.source_id for item in network.source_budgets),
        )

    def test_hardware_sources_have_plain_language_check_labels(self):
        for profile_id in ("battery_problem", "display_problem", "input_problem", "printer_problem"):
            profile = require_profile(profile_id)
            for budget in profile.source_budgets:
                with self.subTest(profile=profile_id, source=budget.source_id):
                    self.assertIn(budget.source_id, SOURCE_LABELS)
                    self.assertNotEqual(SOURCE_LABELS[budget.source_id], budget.source_id)

    def test_application_parameter_is_typed_and_other_profiles_reject_parameters(self):
        application = require_profile("application_failed")
        legacy_application = require_profile("application_failed", 1)
        system_slow = require_profile("system_slow")

        parameters = application.validate_parameters(
            {"application_id": "org.kde.kate", "application_scope": "rpm", "launch_attempted": True}
        )
        self.assertEqual(dict(parameters), {"application_id": "org.kde.kate", "application_scope": "rpm", "launch_attempted": True})
        self.assertEqual(dict(application.validate_parameters({
            "application_id": "app/org.kde.kate/x86_64/stable", "application_scope": "flatpak-user",
        })), {
            "application_id": "app/org.kde.kate/x86_64/stable", "application_scope": "flatpak-user", "launch_attempted": False,
        })
        named = dict(application.validate_parameters({
            "application_id": "app/org.kde.kate/x86_64/stable",
            "application_scope": "flatpak-installation:work-apps",
        }))
        self.assertEqual(named["application_scope"], "flatpak-installation:work-apps")
        self.assertEqual(dict(legacy_application.validate_parameters({"application_id": "org.kde.kate"})), {"application_id": "org.kde.kate"})
        for payload in (
            {},
            {"application_id": "org.kde.kate"},
            {"application_id": 5},
            {"application_id": "/home/person/app"},
            {"application_id": "app/org.kde.kate/x86_64/stable", "application_scope": "rpm"},
            {"application_id": "app/org.kde.kate/x86_64/stable", "application_scope": "flatpak-installation:../escape"},
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
