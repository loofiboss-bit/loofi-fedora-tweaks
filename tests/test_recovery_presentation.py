"""Durable operation outcomes require explicit evidence, never inferred rollback."""
import unittest

from core.actions.recovery_presentation import recovery_presentation


class TestRecoveryPresentation(unittest.TestCase):
    def test_reopened_running_is_interrupted_and_never_offers_retry(self):
        result = recovery_presentation("running", reopened=True)
        self.assertEqual(result.state, "interrupted")
        self.assertEqual(result.outcome, "unknown")
        self.assertEqual(result.next_action, "review")
        self.assertIn("no operation was restarted", result.guidance)

    def test_active_running_is_not_interrupted(self):
        self.assertEqual(recovery_presentation("running").state, "running")

    def test_success_requires_saved_verification(self):
        self.assertEqual(recovery_presentation("succeeded", {"success": True}).state, "verification_failed")
        self.assertEqual(recovery_presentation("succeeded", verification={"success": True}).outcome, "verified")

    def test_partial_and_unavailable_evidence_are_distinct(self):
        partial = {"data": {"missing_packages": ["demo"]}}
        self.assertEqual(recovery_presentation("verification_failed", verification=partial).outcome, "partial")
        partial["data"]["evidence_unavailable"] = True
        self.assertEqual(recovery_presentation("verification_failed", verification=partial).outcome, "unknown")

    def test_expected_failures_have_actionable_explicit_guidance(self):
        for code, text in (("polkit_denied", "Authorization was denied"), ("package_manager_busy", "Wait"),
                           ("no_space", "Free space"), ("network_error", "network connection")):
            with self.subTest(code=code):
                result = recovery_presentation("failed", {"data": {"error_code": code}})
                self.assertIn(text, result.guidance)
                self.assertEqual(result.next_action, "review")
                self.assertEqual(result.outcome, "unknown")

    def test_bad_nested_results_are_safe(self):
        result = recovery_presentation("verification_failed", {"data": []}, {"data": "invalid"})
        self.assertEqual(result.outcome, "unknown")

    def test_cancel_does_not_imply_rollback(self):
        self.assertIn("does not imply rollback", recovery_presentation("cancelled").guidance)

    def test_interrupted_partial_rpm_readback_remains_interrupted(self):
        result = recovery_presentation("interrupted", verification={"data": {"evidence_status": "partial"}})
        self.assertEqual(result.state, "interrupted")
        self.assertEqual(result.outcome, "partial")
        self.assertEqual(result.next_action, "review")
