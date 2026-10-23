"""
Tests for BaseSystemService abstract base class (loofi-fedora-tweaks/services/system/base.py).

Verifies:
- Abstract base class contract enforcement
- TypeError on direct instantiation or incomplete subclassing
- Subclass implementation of abstract methods (reboot, shutdown, suspend, update_grub, set_hostname)
- Argument handling, default keyword arguments, and return types
"""

import os
import sys
import unittest
from inspect import signature

# Add loofi-fedora-tweaks to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'loofi-fedora-tweaks'))

from core.executor.action_result import ActionResult
from services.system.base import BaseSystemService


class DummySystemService(BaseSystemService):
    """Minimal concrete implementation of BaseSystemService for testing."""

    def reboot(self, *, description: str = "", delay_seconds: int = 0) -> ActionResult:
        return ActionResult(
            success=True,
            message=f"Rebooting with description='{description}', delay={delay_seconds}",
        )

    def shutdown(self, *, description: str = "", delay_seconds: int = 0) -> ActionResult:
        return ActionResult(
            success=True,
            message=f"Shutting down with description='{description}', delay={delay_seconds}",
        )

    def suspend(self, *, description: str = "") -> ActionResult:
        return ActionResult(
            success=True,
            message=f"Suspending with description='{description}'",
        )

    def update_grub(self, *, description: str = "") -> ActionResult:
        return ActionResult(
            success=True,
            message=f"Updating GRUB with description='{description}'",
        )

    def set_hostname(self, hostname: str, *, description: str = "") -> ActionResult:
        return ActionResult(
            success=True,
            message=f"Setting hostname to '{hostname}' with description='{description}'",
        )


class TestBaseSystemServiceAbstractContract(unittest.TestCase):
    """Tests abstract contract rules of BaseSystemService."""

    def test_cannot_instantiate_base_class_directly(self):
        """Direct instantiation of BaseSystemService raises TypeError."""
        with self.assertRaises(TypeError):
            BaseSystemService()  # type: ignore[abstract]

    def test_cannot_instantiate_incomplete_subclass(self):
        """Subclass missing abstract methods cannot be instantiated."""

        class IncompleteSystemService(BaseSystemService):
            def reboot(self, *, description: str = "", delay_seconds: int = 0) -> ActionResult:
                return ActionResult(success=True, message="reboot")

        with self.assertRaises(TypeError):
            IncompleteSystemService()  # type: ignore[abstract]

    def test_abstract_methods_set(self):
        """Verify __abstractmethods__ contains all expected abstract operations."""
        expected_abstract_methods = {
            "reboot",
            "shutdown",
            "suspend",
            "update_grub",
            "set_hostname",
        }
        self.assertEqual(BaseSystemService.__abstractmethods__, expected_abstract_methods)


class TestBaseSystemServiceConcreteImplementation(unittest.TestCase):
    """Tests behavior of concrete subclass implementing BaseSystemService."""

    def setUp(self):
        self.service = DummySystemService()

    def test_isinstance_check(self):
        """Concrete subclass instance is recognized as BaseSystemService."""
        self.assertIsInstance(self.service, BaseSystemService)

    def test_reboot_default_args(self):
        """reboot() works with default arguments and returns ActionResult."""
        res = self.service.reboot()
        self.assertTrue(res.success)
        self.assertIn("Rebooting", res.message)

    def test_reboot_custom_args(self):
        """reboot() works with custom description and delay_seconds."""
        res = self.service.reboot(description="Kernel update reboot", delay_seconds=10)
        self.assertTrue(res.success)
        self.assertIn("description='Kernel update reboot'", res.message)
        self.assertIn("delay=10", res.message)

    def test_shutdown_default_args(self):
        """shutdown() works with default arguments and returns ActionResult."""
        res = self.service.shutdown()
        self.assertTrue(res.success)
        self.assertIn("Shutting down", res.message)

    def test_shutdown_custom_args(self):
        """shutdown() works with custom description and delay_seconds."""
        res = self.service.shutdown(description="Scheduled maintenance", delay_seconds=30)
        self.assertTrue(res.success)
        self.assertIn("description='Scheduled maintenance'", res.message)
        self.assertIn("delay=30", res.message)

    def test_suspend_default_args(self):
        """suspend() works with default arguments and returns ActionResult."""
        res = self.service.suspend()
        self.assertTrue(res.success)
        self.assertIn("Suspending", res.message)

    def test_suspend_custom_args(self):
        """suspend() works with custom description."""
        res = self.service.suspend(description="User sleep requested")
        self.assertTrue(res.success)
        self.assertIn("description='User sleep requested'", res.message)

    def test_update_grub_default_args(self):
        """update_grub() works with default arguments and returns ActionResult."""
        res = self.service.update_grub()
        self.assertTrue(res.success)
        self.assertIn("Updating GRUB", res.message)

    def test_update_grub_custom_args(self):
        """update_grub() works with custom description."""
        res = self.service.update_grub(description="Regenerate grub config")
        self.assertTrue(res.success)
        self.assertIn("description='Regenerate grub config'", res.message)

    def test_set_hostname(self):
        """set_hostname() accepts hostname and keyword description."""
        res = self.service.set_hostname("fedora-laptop", description="Set custom hostname")
        self.assertTrue(res.success)
        self.assertIn("Setting hostname to 'fedora-laptop'", res.message)
        self.assertIn("description='Set custom hostname'", res.message)


class TestBaseSystemServiceSignatures(unittest.TestCase):
    """Tests exact method signatures on BaseSystemService class."""

    def test_reboot_signature(self):
        sig = signature(BaseSystemService.reboot)
        params = sig.parameters
        self.assertIn("self", params)
        self.assertIn("description", params)
        self.assertIn("delay_seconds", params)
        self.assertEqual(params["description"].default, "")
        self.assertEqual(params["delay_seconds"].default, 0)

    def test_shutdown_signature(self):
        sig = signature(BaseSystemService.shutdown)
        params = sig.parameters
        self.assertIn("self", params)
        self.assertIn("description", params)
        self.assertIn("delay_seconds", params)
        self.assertEqual(params["description"].default, "")
        self.assertEqual(params["delay_seconds"].default, 0)

    def test_suspend_signature(self):
        sig = signature(BaseSystemService.suspend)
        params = sig.parameters
        self.assertIn("self", params)
        self.assertIn("description", params)
        self.assertEqual(params["description"].default, "")

    def test_update_grub_signature(self):
        sig = signature(BaseSystemService.update_grub)
        params = sig.parameters
        self.assertIn("self", params)
        self.assertIn("description", params)
        self.assertEqual(params["description"].default, "")

    def test_set_hostname_signature(self):
        sig = signature(BaseSystemService.set_hostname)
        params = sig.parameters
        self.assertIn("self", params)
        self.assertIn("hostname", params)
        self.assertIn("description", params)
        self.assertEqual(params["description"].default, "")


if __name__ == "__main__":
    unittest.main()
