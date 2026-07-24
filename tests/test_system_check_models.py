"""Contract tests for the immutable System Check models."""

from __future__ import annotations

import dataclasses
import subprocess
import sys
import unittest

from core.system_check.models import FindingEvidence, SystemCheckResult, SystemFinding


class TestSystemCheckModels(unittest.TestCase):
    def _evidence(self, **facts):
        return FindingEvidence.from_mapping("fixture", facts, collected_at=10.0)

    def test_clean_completed_result_is_immutable(self):
        result = SystemCheckResult(
            "check-1",
            "system-check-quick-v1",
            "completed",
            False,
            10.0,
            11.0,
        )

        self.assertEqual(result.findings, ())
        self.assertEqual(result.to_dict()["state"], "completed")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            result.state = "failed"

    def test_fingerprint_is_deterministic_and_redacted(self):
        first = SystemFinding.build(
            finding_id="state-integrity",
            category="application-state",
            severity="attention",
            title="State needs review",
            summary="Review state",
            evidence=self._evidence(token="secret-value", domain="settings"),
            applicable_variants=frozenset({"traditional", "atomic"}),
            freshness_state="fresh",
            manual_guidance="Review the state.",
            manual_reason_code="state-review",
        )
        second = SystemFinding.build(
            finding_id="state-integrity",
            category="application-state",
            severity="attention",
            title="Changed presentation",
            summary="Changed summary",
            evidence=FindingEvidence.from_mapping(
                "fixture",
                {"domain": "settings", "token": "different-secret"},
                collected_at=20.0,
            ),
            applicable_variants=frozenset({"traditional", "atomic"}),
            freshness_state="fresh",
            manual_guidance="Review the state.",
            manual_reason_code="state-review",
        )

        self.assertEqual(first.fingerprint, second.fingerprint)
        self.assertNotIn("secret-value", str(first.to_dict()))

    def test_evidence_rejects_commands_and_callbacks(self):
        with self.assertRaisesRegex(ValueError, "executable field"):
            self._evidence(command_vector=["systemctl", "restart", "demo.service"])
        with self.assertRaisesRegex(ValueError, "callbacks"):
            self._evidence(handler=lambda: None)

    def test_critical_finding_requires_action_or_manual_guidance(self):
        with self.assertRaisesRegex(ValueError, "Critical findings require"):
            SystemFinding.build(
                finding_id="root-disk-pressure",
                category="storage",
                severity="critical",
                title="Disk pressure",
                summary="Disk is full",
                evidence=self._evidence(root_usage_percent=99),
                applicable_variants=frozenset({"traditional"}),
                freshness_state="fresh",
                route_id="storage",
            )

    def test_every_finding_requires_explicit_variant_applicability(self):
        with self.assertRaisesRegex(ValueError, "applicability"):
            SystemFinding.build(
                finding_id="example",
                category="fixture",
                severity="attention",
                title="Example",
                summary="Example",
                evidence=self._evidence(value=True),
                applicable_variants=frozenset(),
                freshness_state="fresh",
                manual_guidance="Review.",
                manual_reason_code="fixture-review",
            )

    def test_active_result_states_have_no_completion_timestamp(self):
        queued = SystemCheckResult(
            "check-queued",
            "system-check-quick-v1",
            "queued",
            False,
            10.0,
            None,
        )
        running = SystemCheckResult(
            "check-running",
            "system-check-quick-v1",
            "running",
            False,
            10.0,
            None,
        )

        self.assertEqual(queued.state, "queued")
        self.assertEqual(running.state, "running")

    def test_manual_guidance_requires_reason_code(self):
        with self.assertRaisesRegex(ValueError, "reason code"):
            SystemFinding.build(
                finding_id="manual-review",
                category="fixture",
                severity="attention",
                title="Review",
                summary="Review manually",
                evidence=self._evidence(value=True),
                applicable_variants=frozenset({"traditional"}),
                freshness_state="fresh",
                manual_guidance="Review manually.",
            )

    def test_domain_imports_no_pyqt_module(self):
        probe = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import sys; import core.system_check; "
                    "assert not any(name.startswith('PyQt6') for name in sys.modules)"
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        self.assertEqual(probe.returncode, 0, probe.stderr)


if __name__ == "__main__":
    unittest.main()
