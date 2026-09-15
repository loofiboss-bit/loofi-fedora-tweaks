"""v29 task catalog, capability, guidance, and bundle contracts."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))

from core.catalog_models import CapabilityState, FedoraVariant  # noqa: E402
from core.catalog_records.utility import (  # noqa: E402
    action_classifications,
    route_classifications,
    validate_route_classifications,
)
from core.navigation import canonical_utility_route, search_utility_tasks, utility_routes  # noqa: E402
from core.navigation.manifest import all_routes  # noqa: E402
from core.tasks import (  # noqa: E402
    TaskArea,
    TaskBundle,
    TaskCatalog,
    TaskContext,
    TaskDescriptor,
    TaskExecutionMode,
    TuneProfile,
    all_tasks,
    validate_task_catalog,
)


class TestTaskDescriptor(unittest.TestCase):
    def test_default_catalog_has_all_v29_surfaces_and_valid_lifecycle_metadata(self) -> None:
        tasks = all_tasks()
        self.assertTrue({task.area for task in tasks}.issuperset(set(TaskArea)))
        self.assertEqual(validate_task_catalog(), [])
        self.assertEqual(len({task.id for task in tasks}), len(tasks))
        for task in tasks:
            self.assertTrue(task.route_id)
            self.assertTrue(task.preflight)
            self.assertTrue(task.verification)
            self.assertTrue(task.recovery)

    def test_descriptor_round_trip_contains_only_primitive_metadata(self) -> None:
        descriptor = TaskCatalog().get("update:system")
        assert descriptor is not None
        restored = TaskDescriptor.from_dict(descriptor.to_dict())
        self.assertEqual(restored, descriptor)
        self.assertFalse(any(callable(value) for value in descriptor.to_dict().values()))
        self.assertEqual(descriptor.owner_page, "update")
        self.assertEqual(descriptor.risk_level, "medium")

    def test_manual_action_guidance_is_retained_but_never_runnable(self) -> None:
        catalog = TaskCatalog()
        guidance = catalog.get("guidance:enable-flathub")
        self.assertIsNotNone(guidance)
        assert guidance is not None
        self.assertTrue(guidance.manual_only)
        self.assertEqual(guidance.availability, CapabilityState.MANUAL_ONLY)
        self.assertEqual(guidance.execution_mode, TaskExecutionMode.GUIDANCE)
        self.assertNotIn(guidance, catalog.runnable())
        self.assertIn(guidance, catalog.guidance())
        self.assertTrue(guidance.manual_guidance)

    def test_normal_catalog_keeps_read_only_and_handoff_tasks(self) -> None:
        normal = TaskCatalog().normal()
        ids = {task.id for task in normal}
        self.assertIn("fix:system-slow", ids)
        self.assertIn("tune:desktop", ids)
        self.assertNotIn("guidance:enable-flathub", ids)


class TestTaskCapabilityPolicy(unittest.TestCase):
    def test_unknown_backend_fails_closed_for_mutation_but_keeps_diagnostics(self) -> None:
        catalog = TaskCatalog()
        context = TaskContext()
        self.assertNotIn("update:system", {task.id for task in catalog.runnable(context)})
        diagnostic = catalog.eligibility("fix:system-slow", context)
        self.assertEqual(diagnostic.state, CapabilityState.READ_ONLY)
        update = catalog.eligibility("update:system", context)
        self.assertEqual(update.state, CapabilityState.UNAVAILABLE)

    def test_traditional_and_atomic_capability_gates_are_distinct(self) -> None:
        catalog = TaskCatalog()
        traditional = TaskContext(FedoraVariant.TRADITIONAL, frozenset({"fedora", "dnf5"}))
        atomic = TaskContext(FedoraVariant.ATOMIC, frozenset({"fedora", "rpm-ostree"}))
        traditional_ids = {task.id for task in catalog.runnable(traditional)}
        atomic_ids = {task.id for task in catalog.runnable(atomic)}
        self.assertIn("tune:package-cache", traditional_ids)
        self.assertNotIn("tune:package-cache", atomic_ids)
        self.assertIn("tune:storage-trim", atomic_ids)

    def test_pending_reboot_is_explicit_for_reboot_sensitive_tasks(self) -> None:
        catalog = TaskCatalog()
        context = TaskContext(FedoraVariant.TRADITIONAL, frozenset({"fedora", "dnf5"}), pending_reboot=True)
        status = catalog.eligibility("update:system", context)
        self.assertEqual(status.state, CapabilityState.PENDING_REBOOT)
        self.assertNotIn("update:system", {task.id for task in catalog.runnable(context)})


class TestTaskBundlesAndProfiles(unittest.TestCase):
    def test_install_bundle_continues_but_tune_profile_stops(self) -> None:
        install = TaskBundle("install:selection", "Selected applications", "Review selected applications.", ("install:applications",))
        self.assertTrue(install.continue_on_error)
        profile = TuneProfile("tune:test", "Test", "Reviewed test profile.", "recommended", ("tune:storage-trim",))
        self.assertEqual(profile.failure_policy, "stop")
        self.assertFalse(profile.automatic_retry)
        self.assertFalse(profile.automatic_rollback)
        self.assertFalse(profile.automatic_reboot)
        self.assertEqual(profile.to_bundle().failure_policy, "stop")

    def test_contract_rejects_missing_lifecycle_and_automatic_recovery(self) -> None:
        with self.assertRaises(ValueError):
            TaskDescriptor(
                id="bad",
                title="Bad",
                description="Incomplete",
                area=TaskArea.UPDATE,
                route_id="update",
                action_id="update-flatpaks",
            )
        with self.assertRaises(ValueError):
            TaskBundle(
                "bad-bundle",
                "Bad",
                "Automatic retry is forbidden.",
                ("update:system",),
                automatic_retry=True,
            )


class TestUtilityNavigation(unittest.TestCase):
    def test_six_landing_routes_and_legacy_activity_redirects(self) -> None:
        self.assertEqual([route["id"] for route in utility_routes()], ["home", "install", "tune", "fix", "update", "activity"])
        self.assertEqual(canonical_utility_route("changes"), "activity")
        self.assertEqual(canonical_utility_route("maintenance:action-center"), "activity")

    def test_task_search_is_token_order_independent_and_guidance_safe(self) -> None:
        first = search_utility_tasks("flatpak install")
        second = search_utility_tasks("install flatpak")
        self.assertEqual([item.id for item in first], [item.id for item in second])
        self.assertTrue(any(item.task.id == "install:flatpaks" for item in first))
        guidance = search_utility_tasks("flathub", include_guidance=True)
        self.assertTrue(any(item.manual_only for item in guidance))
        runnable = search_utility_tasks("flathub", include_guidance=False)
        self.assertFalse(any(item.manual_only for item in runnable))

    def test_phase_one_inventory_classifies_every_route_and_action(self) -> None:
        routes = route_classifications(route.id for route in all_routes())
        self.assertEqual(validate_route_classifications(routes), [])
        self.assertEqual(len(routes), len(tuple(all_routes())))
        self.assertEqual(routes["maintenance:action-center"], "compatibility_reader")
        self.assertEqual(routes["settings"], "instruction_handoff")
        actions = action_classifications()
        self.assertIn("install-application", actions)
        self.assertEqual(actions["enable-flathub"], "instruction_handoff")


if __name__ == "__main__":
    unittest.main()
