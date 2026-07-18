"""Tests for v15 release checksum, SBOM, and provenance evidence."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.generate_release_evidence import (
    CHECKSUMS_NAME,
    PROVENANCE_NAME,
    SBOM_NAME,
    generate,
    verify,
)


class TestReleaseEvidence(unittest.TestCase):
    def test_generate_and_verify_complete_evidence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "loofi-fedora-tweaks-15.0.0.rpm").write_bytes(b"rpm")
            (root / "loofi_fedora_tweaks-15.0.0.tar.gz").write_bytes(b"sdist")

            result = generate(
                root,
                source_sha="abc123",
                tag="v15.0.0",
                repository="owner/repository",
                workflow_run="https://github.com/owner/repository/actions/runs/1",
            )

            self.assertEqual(
                set(result), {"checksums", "sbom", "provenance"}
            )
            self.assertEqual(
                verify(
                    root,
                    expected_source_sha="abc123",
                    expected_tag="v15.0.0",
                ),
                [],
            )
            provenance = json.loads((root / PROVENANCE_NAME).read_text())
            self.assertEqual(
                provenance["predicateType"], "https://slsa.dev/provenance/v1"
            )
            self.assertEqual(len(provenance["subject"]), 2)
            checksums = (root / CHECKSUMS_NAME).read_text()
            self.assertIn(SBOM_NAME, checksums)
            self.assertIn(PROVENANCE_NAME, checksums)

    def test_verifier_rejects_tampered_artifact_and_wrong_lineage(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifact = root / "artifact.rpm"
            artifact.write_bytes(b"original")
            generate(
                root,
                source_sha="expected",
                tag="v15.0.0",
                repository="owner/repository",
                workflow_run="local",
            )
            artifact.write_bytes(b"tampered")

            errors = verify(
                root,
                expected_source_sha="different",
                expected_tag="v99.0.0",
            )

            self.assertIn("checksum mismatch: artifact.rpm", errors)
            self.assertIn("SBOM subjects do not match release artifacts", errors)
            self.assertIn("provenance subjects do not match release artifacts", errors)
            self.assertIn(
                "provenance source commit does not match expected commit", errors
            )
            self.assertIn("provenance tag does not match expected tag", errors)

    def test_generation_requires_artifacts_and_release_identity(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with self.assertRaises(ValueError):
                generate(
                    root,
                    source_sha="",
                    tag="15.0.0",
                    repository="repository",
                    workflow_run="local",
                )
            (root / "artifact.rpm").write_bytes(b"rpm")
            with self.assertRaises(ValueError):
                generate(
                    root,
                    source_sha="abc",
                    tag="v15.0.0",
                    repository="repository",
                    workflow_run="local",
                )

    def test_auto_release_generates_and_uploads_provenance(self):
        root = Path(__file__).parents[1]
        workflow = (root / ".github" / "workflows" / "auto-release.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("scripts/generate_release_evidence.py release-assets", workflow)
        self.assertIn('--source-sha "$GITHUB_SHA"', workflow)
        self.assertIn("release-assets/*.intoto.jsonl", workflow)


if __name__ == "__main__":
    unittest.main()
