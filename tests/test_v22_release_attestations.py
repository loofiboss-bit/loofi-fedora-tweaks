"""Contracts for V22 GitHub artifact attestations."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "auto-release.yml"


class TestV22ReleaseAttestations(unittest.TestCase):
    def test_release_job_has_attestation_authority_and_current_action(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        release_job = workflow.split("\n  release:\n", 1)[1].split(
            "\n  # Publish to COPR", 1
        )[0]

        self.assertIn("id-token: write", release_job)
        self.assertIn("attestations: write", release_job)
        self.assertIn("uses: actions/attest@v4", release_job)
        self.assertIn("subject-path: release-assets/*", release_job)

    def test_attestation_precedes_publication(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        release_job = workflow.split("\n  release:\n", 1)[1].split(
            "\n  # Publish to COPR", 1
        )[0]

        self.assertLess(
            release_job.index("- name: Attest exact release assets"),
            release_job.index("- name: Publish GitHub Release"),
        )


if __name__ == "__main__":
    unittest.main()
