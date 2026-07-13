from unittest import TestCase

from core.platform import ACTION_CAPABILITIES, capability_for


class TestPlatformCapabilityMatrix(TestCase):
    def test_every_action_has_explicit_traditional_and_atomic_record(self):
        self.assertGreaterEqual(len(ACTION_CAPABILITIES), 10)
        for capability in ACTION_CAPABILITIES.values():
            self.assertIn(capability.traditional, {"supported", "read-only", "unsupported"})
            self.assertIn(capability.atomic, {"supported", "read-only", "unsupported"})
            self.assertTrue(capability.rollback_guidance)
            self.assertTrue(capability.timeout_required)

    def test_atomic_unsupported_action_has_safe_alternative(self):
        support, reason = capability_for("maintenance.autoremove", atomic=True)
        self.assertEqual(support, "unsupported")
        self.assertIn("image-managed", reason)

    def test_traditional_mutation_requires_confirmation_and_verification(self):
        capability = ACTION_CAPABILITIES["package.install"]
        self.assertTrue(capability.confirmation)
        self.assertTrue(capability.verification_required)
