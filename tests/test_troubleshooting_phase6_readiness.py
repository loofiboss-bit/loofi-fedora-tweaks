"""Compass Phase 6 retained evidence and release-gate contracts."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_v23_phase6.py"
SPEC = importlib.util.spec_from_file_location("validate_v23_phase6", SCRIPT)
assert SPEC is not None
assert SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)


class TestV23Phase6Readiness(unittest.TestCase):
    def test_retained_local_candidate_passes_the_release_authorized_gate(self):
        payload = VALIDATOR.run_validation()

        self.assertEqual(payload["status"], "passed", payload["errors"])
        self.assertEqual(payload["errors"], [])

    def test_candidate_cannot_promote_dirty_worktree_to_exact_commit(self):
        payload = json.loads(VALIDATOR.CANDIDATE.read_text(encoding="utf-8"))
        payload["source"]["exact_commit"] = True
        payload["source"]["worktree_clean"] = True

        errors = VALIDATOR.validate_candidate(payload)

        self.assertIn(
            "dirty local candidate must not claim exact clean commit lineage",
            errors,
        )

    def test_release_authorized_gate_does_not_rebind_retained_candidate_to_head(self):
        payload = json.loads(VALIDATOR.CANDIDATE.read_text(encoding="utf-8"))
        payload["source"]["head_commit"] = "0" * 40
        payload["source"]["identity"] = f"WORKTREE@{'0' * 40}"

        errors = VALIDATOR.validate_candidate(payload)

        self.assertNotIn(
            "candidate evidence Git HEAD differs from the checkout",
            errors,
        )

    def test_candidate_requires_all_local_checks_but_keeps_external_checks_false(self):
        payload = json.loads(VALIDATOR.CANDIDATE.read_text(encoding="utf-8"))
        payload["evidence"]["sbom_verified"] = False
        payload["evidence"]["host_install_verified"] = True

        errors = VALIDATOR.validate_candidate(payload)

        self.assertIn("candidate evidence does not prove sbom_verified", errors)
        self.assertIn(
            "candidate evidence must keep host_install_verified false",
            errors,
        )

    def test_authorized_skips_and_external_blockers_are_closed_vocabularies(self):
        payload = json.loads(VALIDATOR.CANDIDATE.read_text(encoding="utf-8"))
        changed = deepcopy(payload)
        changed["skipped_physical_gates"]["fresh_atomic"] = "passed"
        changed["external_blockers"].pop("historical_tag_lineage")

        errors = VALIDATOR.validate_candidate(changed)

        self.assertIn(
            "candidate evidence misstates the skipped physical gates",
            errors,
        )
        self.assertIn(
            "candidate evidence misstates the external blockers",
            errors,
        )

    def test_screenshot_evidence_cannot_claim_a_physical_gate(self):
        payload = json.loads(VALIDATOR.SCREENSHOTS.read_text(encoding="utf-8"))
        payload["capture_policy"]["physical_gate"] = "passed"

        errors = VALIDATOR.validate_screenshots(payload)

        self.assertIn(
            "offscreen screenshot evidence claims a physical gate",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
