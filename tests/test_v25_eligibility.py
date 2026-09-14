"""v25 Proof fail-closed eligibility tests."""

from __future__ import annotations

import unittest
from dataclasses import replace

from core.actions import ActionCatalog, audit_definitions, classify_definition


class TestV25Eligibility(unittest.TestCase):
    def test_catalog_audit_is_complete_for_first_party_definitions(self) -> None:
        catalog = ActionCatalog()
        report = audit_definitions(catalog.list())
        self.assertGreater(len(report), 20)
        self.assertTrue(all("action_id" in item and "reason_code" in item for item in report))
        self.assertTrue(any(item["kind"] == "direct" for item in report))
        self.assertTrue(any(item["kind"] == "review_required" for item in report))

    def test_unknown_action_is_blocked(self) -> None:
        decision = classify_definition(None, action_id="not-registered")
        self.assertEqual(decision.kind, "blocked")
        self.assertFalse(decision.allowed)

    def test_manual_only_stays_guided_and_firmware_uses_one_confirmation(self) -> None:
        catalog = ActionCatalog()
        manual = classify_definition(catalog.get("enable-flathub"))
        self.assertEqual(manual.kind, "review_required")
        self.assertFalse(manual.direct_allowed)

        firmware = classify_definition(catalog.get("update-firmware"))
        self.assertEqual(firmware.kind, "confirmation")
        self.assertTrue(firmware.allowed)
        self.assertTrue(firmware.confirmation_required)
        self.assertEqual(firmware.risk_level, "high")

    def test_normal_updates_are_direct_even_when_their_technical_risk_is_medium(self) -> None:
        catalog = ActionCatalog()
        system = classify_definition(catalog.get("update-fedora-system"))
        flatpak = classify_definition(catalog.get("update-flatpaks"))
        self.assertEqual(system.kind, "direct")
        self.assertEqual(system.risk_level, "medium")
        self.assertEqual(flatpak.kind, "direct")

    def test_recovery_actions_use_one_confirmation_but_keep_high_technical_risk(self) -> None:
        catalog = ActionCatalog()
        for action_id in ("dnf5-history-undo", "rpm-ostree-rollback"):
            with self.subTest(action_id=action_id):
                decision = classify_definition(catalog.get(action_id))
                self.assertEqual(decision.kind, "confirmation")
                self.assertTrue(decision.allowed)
                self.assertEqual(decision.risk_level, "high")

    def test_automatic_policy_cannot_downgrade_high_risk(self) -> None:
        definition = ActionCatalog().get("update-firmware")
        assert definition is not None
        decision = classify_definition(replace(definition, interaction_policy="automatic"))
        self.assertEqual(decision.kind, "review_required")
        self.assertFalse(decision.allowed)

    def test_medium_risk_is_one_confirmation_not_unattended_direct(self) -> None:
        decision = classify_definition(ActionCatalog().get("restart-failed-service"))
        self.assertEqual(decision.kind, "confirmation")
        self.assertTrue(decision.allowed)
        self.assertTrue(decision.confirmation_required)

    def test_incomplete_metadata_fails_closed(self) -> None:
        definition = ActionCatalog().get("dnf-clean-all")
        assert definition is not None
        incomplete = replace(definition, recovery_guidance="")
        decision = classify_definition(incomplete)
        self.assertEqual(decision.kind, "review_required")
        self.assertFalse(decision.allowed)
        self.assertIn("recovery_guidance", decision.facts["metadata_issues"])


if __name__ == "__main__":
    unittest.main()
