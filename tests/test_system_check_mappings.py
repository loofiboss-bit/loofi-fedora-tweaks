"""Deny-by-default tests for finding-to-action mappings."""

from __future__ import annotations

import unittest

from core.system_check.mappings import (
    FindingActionMapping,
    mapped_action,
    validate_finding,
    validate_mappings,
)
from core.system_check.models import FindingEvidence, SystemFinding


class TestSystemCheckMappings(unittest.TestCase):
    def test_canonical_mappings_match_live_catalog(self):
        validate_mappings()

    def test_unknown_action_fails_mapping_gate(self):
        mapping = FindingActionMapping(
            "fixture",
            "retired-action",
            (),
            frozenset({"traditional"}),
        )

        with self.assertRaisesRegex(ValueError, "unknown or retired"):
            validate_mappings(mappings=(mapping,))

    def test_closed_evidence_derives_exact_service_parameter(self):
        action_id, parameters = mapped_action(
            "failed-service",
            {"service": "demo.service", "state": "warning", "ignored": "fact"},
            atomic=False,
        )

        self.assertEqual(action_id, "restart-failed-service")
        self.assertEqual(parameters, {"service": "demo.service"})

    def test_invalid_or_missing_parameter_stays_manual(self):
        self.assertEqual(mapped_action("failed-service", {}, atomic=False), ("", {}))
        self.assertEqual(
            mapped_action("failed-service", {"service": "demo; reboot"}, atomic=False),
            ("", {}),
        )

    def test_materialized_action_must_match_closed_mapping(self):
        evidence = FindingEvidence.from_mapping(
            "maintenance",
            {"service": "demo.service"},
            collected_at=10.0,
        )
        finding = SystemFinding.build(
            finding_id="failed-service",
            category="services",
            severity="attention",
            title="Failed service",
            summary="demo.service failed",
            evidence=evidence,
            applicable_variants=frozenset({"traditional", "atomic"}),
            freshness_state="fresh",
            action_id="dnf-clean-all",
        )

        with self.assertRaisesRegex(ValueError, "not derivable"):
            validate_finding(finding)


if __name__ == "__main__":
    unittest.main()
