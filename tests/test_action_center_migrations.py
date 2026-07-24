"""Action Center schema-v4 migration and future-schema safety."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from core.actions import (
    ActionPlan,
    ActionPlanStore,
    ActionRun,
    ActionRunStore,
    ActionStoreVersionError,
    FindingContext,
    PolicyDecision,
)


def _plan(context=None) -> ActionPlan:
    return ActionPlan(
        plan_id="plan-1",
        action_id="dnf-clean-all",
        parameters={},
        target="44",
        digest="legacy-digest",
        preview=["dnf", "clean", "all"],
        policy_decision=PolicyDecision(True, "preflight_ok", "Ready."),
        risk_level="low",
        privileged=True,
        confirmation_policy="explicit",
        recovery_guidance="Refresh metadata.",
        rollback_supported=True,
        finding_context=context,
    )


def _context() -> FindingContext:
    return FindingContext(
        "check-1",
        "a" * 64,
        "b" * 64,
        "health",
        ("package-cache",),
    )


class TestActionCenterMigrations(unittest.TestCase):
    def test_every_v1_to_v3_plan_store_migrates_atomically_to_v4(self):
        for version in (1, 2, 3):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "plans.json"
                path.write_text(
                    json.dumps({
                        "schema_version": version,
                        "plans": [_plan().to_dict()],
                    }),
                    encoding="utf-8",
                )

                loaded = ActionPlanStore(path).list()

                self.assertEqual(loaded[0].plan_id, "plan-1")
                self.assertIsNone(loaded[0].finding_context)
                self.assertEqual(
                    json.loads(path.read_text(encoding="utf-8"))["schema_version"],
                    4,
                )
                self.assertTrue(path.with_suffix(".json.lkg").exists())

    def test_every_v1_to_v3_run_store_migrates_atomically_to_v4(self):
        for version in (1, 2, 3):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "runs.jsonl"
                run = ActionRun(
                    "run-1",
                    "plan-1",
                    "dnf-clean-all",
                    "correlation-1",
                )
                path.write_text(
                    json.dumps({
                        "action_run_schema_version": version,
                        **run.to_dict(),
                    }) + "\n",
                    encoding="utf-8",
                )

                loaded = ActionRunStore(path).list()

                self.assertEqual(loaded[0].run_id, "run-1")
                self.assertIsNone(loaded[0].finding_context)
                self.assertEqual(
                    json.loads(path.read_text(encoding="utf-8"))[
                        "action_run_schema_version"
                    ],
                    4,
                )
                self.assertTrue(path.with_suffix(".jsonl.lkg").exists())

    def test_v4_context_round_trips_for_plan_and_run(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan_store = ActionPlanStore(root / "plans.json")
            run_store = ActionRunStore(root / "runs.jsonl")
            plan_store.save(_plan(_context()))
            run_store.save(
                ActionRun(
                    "run-1",
                    "plan-1",
                    "dnf-clean-all",
                    "correlation-1",
                    finding_context=_context(),
                )
            )

            self.assertEqual(plan_store.get("plan-1").finding_context, _context())
            self.assertEqual(run_store.get("run-1").finding_context, _context())

    def test_future_plan_and_run_schemas_remain_unmodified(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan_path = root / "plans.json"
            run_path = root / "runs.jsonl"
            plan_payload = {"schema_version": 99, "plans": []}
            run_payload = {"action_run_schema_version": 99, "run_id": "future"}
            plan_path.write_text(json.dumps(plan_payload), encoding="utf-8")
            run_path.write_text(json.dumps(run_payload) + "\n", encoding="utf-8")

            with self.assertRaises(ActionStoreVersionError):
                ActionPlanStore(plan_path).list()
            with self.assertRaises(ActionStoreVersionError):
                ActionRunStore(run_path).list()

            self.assertEqual(
                json.loads(plan_path.read_text(encoding="utf-8")),
                plan_payload,
            )
            self.assertEqual(
                json.loads(run_path.read_text(encoding="utf-8")),
                run_payload,
            )


if __name__ == "__main__":
    unittest.main()
