"""v29 versioned action-bundle contracts."""

from __future__ import annotations

import unittest

from core.actions.bundles import (
    ActionBundle,
    ActionBundleIntegrityError,
    ActionBundleItem,
    ActionBundleSchemaError,
    ActionBundleValidationError,
    BundleItemResult,
    BundleOutcome,
)


class TestActionBundle(unittest.TestCase):
    def test_application_round_trip_preserves_independent_item_policy(self) -> None:
        bundle = ActionBundle.applications(
            (
                ActionBundleItem(
                    "install-application",
                    {"source": "flatpak", "package_id": "org.example.One"},
                ),
                {
                    "action_id": "install-application",
                    "parameters": {"source": "rpm", "package_id": "example-two"},
                },
            ),
            title="Selected applications",
        )

        restored = ActionBundle.from_dict(bundle.to_dict())

        self.assertTrue(restored.is_application_bundle)
        self.assertTrue(restored.continue_on_error)
        self.assertFalse(restored.stop_on_error)
        self.assertEqual([item.position for item in restored.items], [0, 1])
        self.assertEqual([item.item_id for item in restored.items], ["item-1", "item-2"])
        self.assertEqual(restored.digest, bundle.digest)
        self.assertEqual(restored.validate(known_action_ids={"install-application"}), [])

    def test_tune_profile_stops_and_unknown_actions_fail_review(self) -> None:
        bundle = ActionBundle.tune_profile(
            ("fstrim-all", "dnf-clean-all"),
            bundle_id="tune-recommended",
        )

        self.assertTrue(bundle.is_tune_profile)
        self.assertTrue(bundle.stop_on_error)
        self.assertEqual(bundle.validate(known_action_ids={"fstrim-all"}), ["unknown_action:dnf-clean-all"])
        with self.assertRaises(ActionBundleValidationError):
            bundle.assert_valid(known_action_ids={"fstrim-all"})

    def test_tampered_and_future_bundles_fail_closed(self) -> None:
        payload = ActionBundle.applications(("install-application",)).to_dict()
        payload["title"] = "Tampered"
        with self.assertRaises(ActionBundleIntegrityError):
            ActionBundle.from_dict(payload)
        policy_payload = ActionBundle.applications(("install-application",)).to_dict()
        policy_payload["execution_policy"] = "stop_on_error"
        with self.assertRaises(ActionBundleValidationError):
            ActionBundle.from_dict(policy_payload)
        with self.assertRaises(ActionBundleSchemaError):
            ActionBundle.from_dict({"schema": "loofi.action-bundle/v99", "items": []})
        with self.assertRaises(ActionBundleSchemaError):
            ActionBundle.from_dict({"schema_version": "future", "items": []})

    def test_invalid_structure_and_policy_are_rejected(self) -> None:
        with self.assertRaises(ActionBundleValidationError):
            ActionBundle("unknown", ("fstrim-all",))
        with self.assertRaises(ActionBundleValidationError):
            ActionBundle("application_install", ())
        with self.assertRaises(ActionBundleValidationError):
            ActionBundle(
                "application_install",
                ("install-application",),
                execution_policy="stop_on_error",
            )
        with self.assertRaises(ActionBundleValidationError):
            ActionBundleItem("bad action id")
        with self.assertRaises(ActionBundleValidationError):
            ActionBundle.from_dict({"kind": "application_install", "items": "not-a-list"})

    def test_bundle_outcome_keeps_per_item_results(self) -> None:
        succeeded = BundleItemResult("one", "install-application", "verified", "Installed")
        failed = BundleItemResult("two", "install-application", "failed", "Unavailable")
        skipped = BundleItemResult("three", "install-application", "skipped", "Not attempted", skipped=True)
        outcome = BundleOutcome(
            "apps",
            "application_install",
            "continue_on_error",
            "partial_failure",
            "One application failed.",
            (succeeded, failed, skipped),
        )

        self.assertTrue(succeeded.success)
        self.assertFalse(outcome.success)
        self.assertTrue(outcome.partial)
        self.assertEqual(outcome.failed_items, (failed,))
        self.assertEqual(outcome.to_dict()["items"][2]["skipped"], True)


if __name__ == "__main__":
    unittest.main()
