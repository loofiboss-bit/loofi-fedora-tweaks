"""Tests for v12 observability redaction."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))

from core.observability.privacy import redact_payload


class TestObservabilityRedaction(unittest.TestCase):
    """Private values are removed recursively."""

    def test_recursive_redaction(self):
        payload = {
            "path": "/home/loofi/file.txt",
            "email": "user@example.com",
            "nested": {"token": "abc", "line": "api_key=secret"},
        }
        text = json.dumps(redact_payload(payload))

        self.assertNotIn("/home/loofi", text)
        self.assertNotIn("user@example.com", text)
        self.assertNotIn("api_key=secret", text)
        self.assertEqual(redact_payload(payload)["nested"]["token"], "<masked>")


if __name__ == "__main__":
    unittest.main()

