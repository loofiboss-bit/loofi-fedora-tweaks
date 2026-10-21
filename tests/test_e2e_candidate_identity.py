"""A later build must not silently replace an in-flight VM candidate."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from e2e.vm import FedoraE2E, VMError


class CandidateIdentityTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="loofi-candidate-test-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        reports = self.root / "reports"
        reports.mkdir()
        self.vm = FedoraE2E(self.root / "vm", reports)
        self.original = self.root / "fixture.rpm"
        self.original.write_bytes(b"the reviewed candidate")

    def test_shared_build_output_can_change_without_replacing_retained_candidate(self):
        retained = self.vm._retain_candidate(self.original)
        self.original.write_bytes(b"a subsequent build")
        self.assertEqual(retained.read_bytes(), b"the reviewed candidate")
        self.assertEqual(retained.name, self.original.name)
        self.assertEqual(retained.stat().st_mode & 0o777, 0o400)
        self.assertEqual(retained.parent.stat().st_mode & 0o777, 0o700)

    def test_repeated_builds_keep_separate_artifacts(self):
        first = self.vm._retain_candidate(self.original)
        self.original.write_bytes(b"a subsequent build")
        second = self.vm._retain_candidate(self.original)
        self.assertNotEqual(first, second)
        self.assertEqual(first.read_bytes(), b"the reviewed candidate")
        self.assertEqual(second.read_bytes(), b"a subsequent build")

    @patch("e2e.vm.FedoraE2E._guest_exec")
    @patch("e2e.vm.FedoraE2E._write_guest_file")
    def test_changed_retained_candidate_is_rejected_before_any_guest_operation(self, transfer, execute):
        retained = self.vm._retain_candidate(self.original)
        self.vm._rpm_evidence = {"sha256": hashlib.sha256(retained.read_bytes()).hexdigest()}
        retained.chmod(0o600)
        retained.write_bytes(b"modified retained bytes")
        with self.assertRaisesRegex(VMError, "changed before staging"):
            self.vm._prepare_payload(retained)
        transfer.assert_not_called()
        execute.assert_not_called()
