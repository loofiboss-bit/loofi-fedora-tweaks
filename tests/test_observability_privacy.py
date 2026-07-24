"""Version-neutral privacy gate for persisted and exported evidence."""

from __future__ import annotations

import unittest

from core.privacy import redact_payload, redact_text


class TestObservabilityPrivacy(unittest.TestCase):
    def test_masks_paths_identity_secrets_and_network_identifiers(self):
        payload = {
            "path": "/home/alice/private/report.txt",
            "message": (
                "host=workstation email=a@example.com "
                "token=private ip=192.168.1.44 "
                "ipv6=2001:db8::44 mac=aa:bb:cc:dd:ee:ff"
            ),
            "api_key": "private",
        }

        redacted = str(redact_payload(payload))

        for private in (
            "/home/alice",
            "a@example.com",
            "token=private",
            "192.168.1.44",
            "2001:db8::44",
            "aa:bb:cc:dd:ee:ff",
            "'api_key': 'private'",
        ):
            with self.subTest(private=private):
                self.assertNotIn(private, redacted)

    def test_redaction_is_bounded(self):
        self.assertEqual(len(redact_text("x" * 7000)), 6000)


if __name__ == "__main__":
    unittest.main()
