"""Explicit downloads remain scoped and independently verify cached metadata."""
import unittest
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.actions.application_metadata import _preflight, _render, _validate, _verify, metadata_refresh_definition


class TestApplicationMetadataRefresh(unittest.TestCase):
    def runtime(self):
        return SimpleNamespace(is_atomic=Mock(return_value=False), package_manager=Mock(return_value="dnf5"), package_manager_busy=Mock(return_value=False), execute_read_only=Mock())

    def test_closed_parameters_reject_arbitrary_command_options(self):
        for parameters in ({"source": "flatpak", "installation": "user", "remote": "--help"}, {"source": "fedora", "command": "install"}, {"source": "flatpak", "installation": "../../system", "remote": "flathub"}):
            self.assertFalse(_validate(parameters).allowed)

    def test_fixed_vectors_never_install_or_update_applications(self):
        runtime = self.runtime()
        self.assertEqual(_render({"source": "fedora"}, runtime), ["dnf5", "--assumeno", "makecache", "--refresh"])
        self.assertEqual(_render({"source": "flatpak", "installation": "office", "remote": "private"}, runtime), ["flatpak", "update", "--appstream", "--noninteractive", "--installation=office", "private"])
        definition = metadata_refresh_definition()
        self.assertTrue(definition.privilege_resolver({"source": "fedora"}, runtime))
        self.assertFalse(definition.privilege_resolver({"source": "flatpak"}, runtime))

    def test_unknown_or_disabled_flatpak_remote_cannot_refresh(self):
        runtime = self.runtime()
        parameters = {"source": "flatpak", "installation": "user", "remote": "flathub"}
        runtime.execute_read_only.return_value = SimpleNamespace(success=True, stdout="flathub\thttps://example.test\tdisabled\n")
        self.assertFalse(_preflight(parameters, runtime).allowed)
        runtime.execute_read_only.return_value = SimpleNamespace(success=True, stdout="other\thttps://example.test\t\n")
        self.assertFalse(_preflight(parameters, runtime).allowed)

    def test_verification_requires_same_source_and_readable_cache(self):
        runtime = self.runtime()
        parameters = {"source": "flatpak", "installation": "user", "remote": "flathub"}
        config = SimpleNamespace(success=True, stdout="flathub\thttps://example.test\t\n")
        runtime.execute_read_only.return_value = config
        decision = _preflight(parameters, runtime)
        self.assertTrue(decision.allowed)
        plan = SimpleNamespace(parameters=parameters, policy_decision=decision)
        runtime.execute_read_only.side_effect = [config, SimpleNamespace(success=False, stdout="")]
        self.assertEqual(_verify(None, plan, runtime).state, "failed")
        runtime.execute_read_only.side_effect = [config, SimpleNamespace(success=True, stdout="org.example.App\tstable\tx86_64\n")]
        self.assertEqual(_verify(None, plan, runtime).state, "succeeded")
        runtime.execute_read_only.side_effect = [SimpleNamespace(success=True, stdout="flathub\thttps://changed.test\t\n")]
        self.assertEqual(_verify(None, plan, runtime).state, "failed")

    def test_atomic_and_package_lock_fail_closed(self):
        runtime = self.runtime()
        runtime.is_atomic.return_value = True
        self.assertFalse(_preflight({"source": "fedora"}, runtime).allowed)
        runtime.is_atomic.return_value = False
        runtime.package_manager_busy.return_value = True
        self.assertFalse(_preflight({"source": "fedora"}, runtime).allowed)
        runtime.execute_read_only.assert_not_called()

    def test_rpm_source_endpoint_or_key_drift_invalidates_review(self):
        runtime = self.runtime()
        parameters = {"source": "fedora"}
        original = SimpleNamespace(success=True, stdout=json.dumps({"available": True, "enabled_count": 2, "repository_digest": "a" * 64}))
        runtime.execute_read_only.return_value = original
        decision = _preflight(parameters, runtime)
        self.assertTrue(decision.allowed)
        self.assertEqual(runtime.execute_read_only.call_args.args[0][1:], ["sources"])
        changed = SimpleNamespace(success=True, stdout=json.dumps({"available": True, "enabled_count": 2, "repository_digest": "b" * 64}))
        runtime.execute_read_only.return_value = changed
        self.assertEqual(_verify(None, SimpleNamespace(parameters=parameters, policy_decision=decision), runtime).state, "failed")

    def test_rpm_config_inspection_does_not_require_populated_cache(self):
        runtime = self.runtime()
        runtime.execute_read_only.return_value = SimpleNamespace(success=True, stdout=json.dumps({"available": True, "enabled_count": 1, "repository_digest": "a" * 64}))
        self.assertTrue(_preflight({"source": "fedora"}, runtime).allowed)
        self.assertNotIn("repoquery", runtime.execute_read_only.call_args.args[0])


    @patch("services.software.application_discovery.rpm_appstream_catalog_available")
    def test_rpm_cache_success_cannot_hide_missing_or_invalid_appstream(self, catalog):
        runtime = self.runtime()
        config = SimpleNamespace(success=True, stdout=json.dumps({"available": True, "enabled_count": 1, "repository_digest": "a" * 64}))
        runtime.execute_read_only.return_value = config
        parameters = {"source": "fedora"}
        decision = _preflight(parameters, runtime)
        plan = SimpleNamespace(parameters=parameters, policy_decision=decision)
        for available in (False, True):
            with self.subTest(catalog_available=available):
                catalog.return_value = available
                runtime.execute_read_only.side_effect = [config, SimpleNamespace(success=True, stdout="fedora-release\tfedora\n")]
                result = _verify(None, plan, runtime)
                self.assertEqual(result.state, "succeeded" if available else "failed")
                self.assertIn("separately", result.message)
        self.assertEqual(catalog.call_count, 2)
        self.assertIn("separate reviewed package update", decision.explanation)
        self.assertEqual(_render(parameters, runtime), ["dnf5", "--assumeno", "makecache", "--refresh"])
