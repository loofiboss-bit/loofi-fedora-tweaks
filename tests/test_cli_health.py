"""Tests for v12 health CLI commands."""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))


def _args(**kwargs):
    args = MagicMock()
    for key, value in kwargs.items():
        setattr(args, key, value)
    if "json" not in kwargs:
        args.json = False
    return args


class TestCliHealthCommands(unittest.TestCase):
    """Health CLI commands return stable JSON payloads."""

    @patch("cli.main._output_json")
    @patch("cli.main._json_output", True)
    @patch("core.observability.ObservabilityService")
    def test_health_snapshot_json(self, service_cls, mock_output_json):
        from cli.main import cmd_health

        snapshot = MagicMock()
        snapshot.to_dict.return_value = {"schema_version": 1, "fedora_target": "44"}
        service_cls.return_value.collect_snapshot.return_value = snapshot
        service_cls.return_value.snapshots.load.return_value = [snapshot]

        result = cmd_health(_args(health_action="snapshot", target="44"))

        self.assertEqual(result, 0)
        payload = mock_output_json.call_args.args[0]
        self.assertEqual(payload["schema_version"], 1)
        self.assertIn("snapshot", payload)
        service_cls.return_value.collect_snapshot.assert_called_once_with(target="44", source="cli")

    @patch("cli.main._output_json")
    @patch("cli.main._json_output", True)
    @patch("core.observability.HealthTimelineStore")
    def test_health_timeline_json_empty(self, mock_store_cls, mock_output_json):
        from cli.main import cmd_health

        mock_store_cls.return_value.export.return_value = {
            "schema_version": 1,
            "count": 0,
            "trend_summary": {"summary": "No health snapshots recorded."},
            "snapshots": [],
        }

        result = cmd_health(_args(health_action="timeline", limit=10))

        self.assertEqual(result, 0)
        self.assertEqual(mock_output_json.call_args.args[0]["count"], 0)

    @patch("cli.main._output_json")
    @patch("cli.main._json_output", True)
    @patch("core.actions.ActionCenterService.recommendations_from_timeline", return_value=[])
    @patch("core.actions.ActionCenterService.candidates_from_readiness", return_value=[])
    def test_action_center_recommendations_json(self, _mock_candidates, _mock_recommendations, mock_output_json):
        from cli.main import cmd_action_center

        result = cmd_action_center(_args(action="recommendations", target="44", limit=10))

        self.assertEqual(result, 0)
        self.assertEqual(mock_output_json.call_args.args[0]["schema_version"], 3)

    @patch("cli.main._output_json")
    @patch("cli.main._json_output", True)
    @patch("core.actions.ActionCenterOrchestrator")
    def test_action_center_plan_json_envelope(self, orchestrator_cls, mock_output_json):
        from cli.main import cmd_action_center

        policy = MagicMock()
        policy.to_dict.return_value = {"allowed": True, "reason_code": "preflight_ok"}
        plan = MagicMock(
            plan_id="plan-1",
            action_id="restart-failed-service",
            state="needs_review",
            preview=["systemctl", "restart", "broken.service"],
            expires_at=2000.0,
            policy_decision=policy,
        )
        plan.to_dict.return_value = {"plan_id": "plan-1", "state": "needs_review"}
        orchestrator_cls.return_value.plan.return_value = plan

        result = cmd_action_center(
            _args(
                action="plan",
                action_id="restart-failed-service",
                target="44",
                service="broken.service",
            )
        )

        self.assertEqual(result, 0)
        orchestrator_cls.return_value.plan.assert_called_once_with(
            "restart-failed-service",
            {"service": "broken.service"},
            target="44",
        )
        payload = mock_output_json.call_args.args[0]
        self.assertEqual(payload["schema_version"], 3)
        self.assertEqual(payload["plan"]["plan_id"], "plan-1")
        self.assertEqual(payload["policy_decision"]["reason_code"], "preflight_ok")

    @patch("cli.main._output_json")
    @patch("cli.main._json_output", True)
    @patch("core.actions.ActionCenterOrchestrator")
    def test_action_center_apply_and_verify_keep_separate_run_states(self, orchestrator_cls, mock_output_json):
        from cli.main import cmd_action_center

        policy = MagicMock()
        policy.to_dict.return_value = {"allowed": True, "reason_code": "preflight_ok"}
        plan = MagicMock(policy_decision=policy)
        run = MagicMock(
            run_id="run-1",
            plan_id="plan-1",
            action_id="dnf-clean-all",
            state="verifying",
            recovery_status="available",
        )
        run.to_dict.return_value = {"run_id": "run-1", "state": "verifying"}
        orchestrator_cls.return_value.get_plan.return_value = plan
        orchestrator_cls.return_value.apply.return_value = run

        applied = cmd_action_center(
            _args(
                action="apply",
                action_id="plan-1",
                target="44",
                confirm=True,
                accept_no_rollback=False,
            )
        )

        self.assertEqual(applied, 0)
        orchestrator_cls.return_value.apply.assert_called_once()
        self.assertEqual(mock_output_json.call_args.args[0]["run"]["state"], "verifying")

        run.state = "succeeded"
        run.to_dict.return_value = {"run_id": "run-1", "state": "succeeded"}
        orchestrator_cls.return_value.verify.return_value = run
        verified = cmd_action_center(_args(action="verify", action_id="run-1", target="44"))

        self.assertEqual(verified, 0)
        orchestrator_cls.return_value.verify.assert_called_once_with("run-1")
        self.assertEqual(mock_output_json.call_args.args[0]["run"]["state"], "succeeded")


class TestCliHealthTextAndStateBranches(unittest.TestCase):
    """Exercise the human-readable and failure branches of v14 CLI surfaces."""

    @patch("cli.main._print")
    @patch("cli.main._output_json")
    @patch("core.state.StateArchiveService")
    @patch("core.state.StateDoctor")
    def test_state_doctor_backup_restore_and_invalid_paths(self, doctor_cls, archive_cls, output_json, print_fn):
        from cli.main import cmd_state

        doctor_cls.return_value.run.return_value = {"status": "ok"}
        self.assertEqual(cmd_state(SimpleNamespace(state_action="doctor")), 0)

        archive_cls.return_value.backup.return_value = {"status": "error"}
        self.assertEqual(cmd_state(SimpleNamespace(state_action="backup", output="~/state.zip")), 1)

        archive_cls.return_value.plan_restore.return_value = {"status": "planned"}
        self.assertEqual(
            cmd_state(SimpleNamespace(state_action="restore", archive="~/state.zip", restore_action="plan", plan_id=None)),
            0,
        )
        self.assertEqual(
            cmd_state(SimpleNamespace(state_action="restore", archive="~/state.zip", restore_action="apply", plan_id=None)),
            2,
        )

        archive_cls.return_value.apply_restore.return_value = {"status": "restored"}
        self.assertEqual(
            cmd_state(SimpleNamespace(state_action="restore", archive="~/state.zip", restore_action="apply", plan_id="plan-1")),
            0,
        )
        self.assertEqual(cmd_state(SimpleNamespace(state_action="invalid")), 2)
        self.assertGreaterEqual(output_json.call_count, 4)
        self.assertEqual(print_fn.call_args_list[-1].args[0], "Choose doctor, backup, or restore")

    @patch("cli.main._print")
    @patch("cli.main._json_output", False)
    @patch("core.observability.MaintenanceTrendAnalyzer")
    @patch("core.observability.ObservabilityService")
    def test_health_snapshot_text(self, service_cls, analyzer_cls, print_fn):
        from cli.main import cmd_health

        snapshot = MagicMock()
        snapshot.to_dict.return_value = {"timestamp": "now"}
        service_cls.return_value.collect_snapshot.return_value = snapshot
        service_cls.return_value.snapshots.load.return_value = [snapshot]
        analyzer_cls.return_value.analyze.return_value.to_dict.return_value = {"summary": "Stable"}

        self.assertEqual(cmd_health(SimpleNamespace(health_action="snapshot", target="44")), 0)
        print_fn.assert_any_call("My Fedora Today snapshot recorded.")
        print_fn.assert_any_call("Stable")

    @patch("cli.main._print")
    @patch("cli.main._json_output", False)
    @patch("core.observability.HealthTimelineStore")
    def test_health_timeline_text(self, store_cls, print_fn):
        from cli.main import cmd_health

        store_cls.return_value.export.return_value = {
            "count": 1,
            "trend_summary": {"summary": "Improving"},
            "snapshots": [{"timestamp": "today", "app_version": "14.0.0", "app_codename": "Helm"}],
        }

        self.assertEqual(cmd_health(SimpleNamespace(health_action="timeline", limit=5)), 0)
        print_fn.assert_any_call("Snapshots: 1")
        print_fn.assert_any_call("- today: 14.0.0 Helm")

    @patch("cli.main._print")
    @patch("cli.main._json_output", False)
    def test_maintenance_unknown_text(self, print_fn):
        from cli.main import cmd_maintenance

        self.assertEqual(cmd_maintenance(SimpleNamespace(maintenance_action="bad", json=False)), 1)
        print_fn.assert_called_with("Unknown maintenance command: bad")

    @patch("cli.main._output_json")
    @patch("cli.main._json_output", True)
    def test_maintenance_unknown_json(self, output_json):
        from cli.main import cmd_maintenance

        self.assertEqual(cmd_maintenance(SimpleNamespace(maintenance_action="bad", json=False)), 1)
        output_json.assert_called_with({"schema_version": 1, "error": "unknown_maintenance_command", "action": "bad"})

    @patch("cli.main._output_json")
    @patch("cli.main._print")
    @patch("cli.main._json_output", False)
    @patch("core.observability.MaintenanceTrendAnalyzer")
    @patch("core.observability.HealthTimelineStore")
    @patch("core.observability.HealthSnapshot")
    @patch("core.diagnostics.daily_maintenance.DailyMaintenanceService")
    @patch("core.actions.ActionCenterService")
    def test_maintenance_today_text_and_json(
        self,
        action_service_cls,
        daily_cls,
        snapshot_cls,
        timeline_cls,
        analyzer_cls,
        print_fn,
        output_json,
    ):
        from cli.main import cmd_maintenance

        report = SimpleNamespace(
            recommended_action="Review one item",
            cards=[SimpleNamespace(title="Updates", state="ok", summary="Current")],
            to_dict=lambda: {"status": "ok"},
        )
        snapshot = SimpleNamespace(to_dict=lambda: {"timestamp": "now"})
        daily_cls.return_value.collect.return_value = report
        action_service_cls.return_value.candidates_from_readiness.return_value = []
        snapshot_cls.from_daily_maintenance.return_value = snapshot
        timeline_cls.return_value.load.return_value = []
        analyzer_cls.return_value.analyze.return_value.to_dict.return_value = {"summary": "Stable"}

        self.assertEqual(cmd_maintenance(SimpleNamespace(maintenance_action="today", target="44", json=False)), 0)
        print_fn.assert_any_call("My Fedora Today")
        print_fn.assert_any_call("- Updates: ok - Current")

        self.assertEqual(cmd_maintenance(SimpleNamespace(maintenance_action="today", target="44", json=True)), 0)
        self.assertEqual(output_json.call_args.args[0]["schema_version"], 1)


class TestCliReadinessPresentationBranches(unittest.TestCase):
    @staticmethod
    def _report(status="ready"):
        check = SimpleNamespace(
            status="warn",
            title="Package health",
            summary="Review packages",
            beginner_guidance="Open Action Center",
            recommendation=SimpleNamespace(title="Clean metadata"),
            command_preview=["dnf", "check"],
            advanced_detail="details",
        )
        return SimpleNamespace(
            target="Fedora 44",
            score=91,
            status=status,
            summary="Ready with guidance",
            checks=[check],
            to_dict=lambda advanced=False: {"status": status, "advanced": advanced},
        )

    @patch("cli.main._print")
    @patch("cli.main._json_output", False)
    def test_readiness_text_advanced_and_blocked_exit(self, print_fn):
        from cli.main import _print_readiness_report

        self.assertEqual(_print_readiness_report(self._report("blocked"), advanced=True), 1)
        print_fn.assert_any_call("  Command: dnf check")
        print_fn.assert_any_call("  Detail: details")

    @patch("cli.main._output_json")
    @patch("cli.main._json_output", True)
    def test_readiness_json_preview_exit(self, output_json):
        from cli.main import _print_readiness_report

        self.assertEqual(_print_readiness_report(self._report("preview"), advanced=False), 0)
        output_json.assert_called_with({"status": "preview", "advanced": False})

    @patch("cli.main._print")
    @patch("cli.main._json_output", False)
    @patch("core.diagnostics.release_readiness.ReleaseReadiness.build_release_plan")
    def test_release_plan_text_sections(self, build_plan, print_fn):
        from cli.main import _print_release_plan

        build_plan.return_value = {
            "summary": "Review before upgrade",
            "next_action": "Run checks",
            "target_changes": {
                "important_changes": [{"title": "Python", "summary": "3.14"}],
                "known_risks": [{"title": "Extensions", "summary": "Review compatibility"}],
            },
            "attention": [{"id": "packages", "summary": "Resolve packages"}],
        }
        self.assertEqual(_print_release_plan(self._report()), 0)
        print_fn.assert_any_call("- Python: 3.14")
        print_fn.assert_any_call("- Extensions: Review compatibility")
        print_fn.assert_any_call("- packages: Resolve packages")

    @patch("cli.main._output_json")
    @patch("cli.main._json_output", True)
    @patch("core.diagnostics.release_readiness.ReleaseReadiness.build_release_plan", return_value={"summary": "ok"})
    def test_release_plan_json(self, _build_plan, output_json):
        from cli.main import _print_release_plan

        self.assertEqual(_print_release_plan(self._report()), 0)
        output_json.assert_called_with({"summary": "ok"})

    @patch("cli.main._print")
    @patch("cli.main._json_output", False)
    def test_action_result_text_candidate_and_failure(self, print_fn):
        from cli.main import _print_action_result

        result = SimpleNamespace(
            success=False,
            message="Blocked",
            data={
                "candidate": {
                    "command_preview": ["dnf", "clean", "all"],
                    "risk_level": "medium",
                    "privileged": True,
                    "manual_only": False,
                    "revert_hint": "Refresh metadata",
                }
            },
            to_dict=lambda: {"success": False},
        )
        self.assertEqual(_print_action_result(result), 1)
        print_fn.assert_any_call("Command preview: dnf clean all")
        print_fn.assert_any_call("Rollback: Refresh metadata")

    @patch("cli.main._output_json")
    @patch("cli.main._json_output", True)
    def test_action_result_json_success(self, output_json):
        from cli.main import _print_action_result

        result = SimpleNamespace(success=True, message="OK", data=None, to_dict=lambda: {"success": True})
        self.assertEqual(_print_action_result(result), 0)
        output_json.assert_called_with({"success": True})


class TestCliReadinessActionBranches(unittest.TestCase):
    @staticmethod
    def _candidate():
        return SimpleNamespace(
            id="dnf-clean-all",
            title="Clean DNF metadata",
            manual_only=False,
            risk_level="medium",
            explanation="Reclaims cache space",
            command_preview=["dnf", "clean", "all"],
            related_check_id="packages",
            privileged=True,
            revert_hint="Refresh metadata",
            verification_command=["dnf", "repolist"],
            docs_link="https://example.invalid/docs",
            to_dict=lambda: {"id": "dnf-clean-all"},
        )

    @patch("cli.main._print")
    @patch("cli.main._json_output", False)
    @patch("core.diagnostics.readiness_actions.ReadinessActionService")
    def test_actions_and_action_info_text(self, service, print_fn):
        from cli.main import _cmd_readiness_action

        candidate = self._candidate()
        service.build_plan.return_value = SimpleNamespace(target="Fedora 44", candidates=[candidate])
        self.assertEqual(
            _cmd_readiness_action(SimpleNamespace(readiness_action="actions", action_id="", target="44")),
            0,
        )
        print_fn.assert_any_call("  Preview: dnf clean all")

        service.get_candidate.return_value = candidate
        self.assertEqual(
            _cmd_readiness_action(SimpleNamespace(readiness_action="action-info", action_id=candidate.id, target="44")),
            0,
        )
        print_fn.assert_any_call("Rollback: Refresh metadata")
        print_fn.assert_any_call("Verify: dnf repolist")

    @patch("cli.main._print")
    @patch("cli.main._json_output", False)
    @patch("core.diagnostics.release_readiness.ReleaseReadiness")
    def test_explain_text_found_and_missing(self, readiness_cls, print_fn):
        from cli.main import _cmd_readiness_action

        args = SimpleNamespace(readiness_action="explain", action_id="packages", target="44")
        readiness_cls.explain_check.return_value = None
        self.assertEqual(_cmd_readiness_action(args), 1)
        print_fn.assert_any_call("Readiness check not found: packages")

        readiness_cls.explain_check.return_value = {
            "check": {
                "id": "packages",
                "title": "Packages",
                "summary": "Review",
                "beginner_guidance": "Open the report",
                "command_preview": ["dnf", "check"],
                "advanced_detail": "full detail",
            }
        }
        self.assertEqual(_cmd_readiness_action(args), 0)
        print_fn.assert_any_call("Command: dnf check")
        print_fn.assert_any_call("Detail: full detail")

    @patch("cli.main._output_json")
    @patch("cli.main._json_output", True)
    @patch("core.diagnostics.release_readiness.ReleaseReadiness")
    def test_explain_json_found_and_missing(self, readiness_cls, output_json):
        from cli.main import _cmd_readiness_action

        args = SimpleNamespace(readiness_action="explain", action_id="missing", target="44")
        readiness_cls.explain_check.return_value = None
        self.assertEqual(_cmd_readiness_action(args), 1)
        output_json.assert_called_with({"error": "not_found", "check_id": "missing"})

        readiness_cls.explain_check.return_value = {"check": {"id": "packages"}}
        self.assertEqual(_cmd_readiness_action(args), 0)
        output_json.assert_called_with({"check": {"id": "packages"}})

    @patch("cli.main._print")
    @patch("cli.main._json_output", False)
    @patch("core.export.support_bundle.SupportBundleWriter")
    def test_export_text(self, bundle_cls, print_fn):
        from cli.main import _cmd_readiness_action

        self.assertEqual(
            _cmd_readiness_action(SimpleNamespace(readiness_action="export", action_id="", target="44", path="bundle.json")),
            0,
        )
        bundle_cls.save_json.assert_called_once_with("bundle.json", target="44")
        print_fn.assert_called_with("Exported readiness support bundle: bundle.json")

    @patch("cli.main._output_json")
    @patch("cli.main._json_output", True)
    @patch("core.export.support_bundle.SupportBundleWriter")
    def test_export_and_action_info_json(self, bundle_cls, output_json):
        from cli.main import _cmd_readiness_action

        bundle_cls.generate_bundle.return_value = {"schema_version": 10}
        self.assertEqual(
            _cmd_readiness_action(SimpleNamespace(readiness_action="export", action_id="", target="44", path=None)),
            0,
        )
        output_json.assert_called_with({"schema_version": 10})

    @patch("cli.main._print")
    @patch("cli.main._json_output", False)
    @patch("cli.commands.readiness_commands._print_action_result", return_value=0)
    @patch("core.diagnostics.readiness_actions.ReadinessActionService")
    def test_preview_run_verify_and_unknown_text(self, service, print_result, print_fn):
        from cli.main import _cmd_readiness_action

        service.preview.return_value = object()
        service.run.return_value = object()
        service.verify.return_value = object()
        for action in ("action-preview", "action-run", "action-verify"):
            self.assertEqual(
                _cmd_readiness_action(
                    SimpleNamespace(readiness_action=action, action_id="dnf-clean-all", target="44", confirm=True)
                ),
                0,
            )
        service.run.assert_called_once_with("dnf-clean-all", target_key="44", confirm=True)
        self.assertEqual(
            _cmd_readiness_action(SimpleNamespace(readiness_action="bad", action_id="", target="44")),
            1,
        )
        print_fn.assert_called_with("Unknown readiness action command: bad")
        self.assertEqual(print_result.call_count, 3)

    @patch("cli.main._output_json")
    @patch("cli.main._json_output", True)
    @patch("core.diagnostics.readiness_actions.ReadinessActionService")
    def test_actions_action_info_missing_and_unknown_json(self, service, output_json):
        from cli.main import _cmd_readiness_action

        service.build_plan.return_value = SimpleNamespace(target="Fedora 44", candidates=[], to_dict=lambda: {"candidates": []})
        self.assertEqual(
            _cmd_readiness_action(SimpleNamespace(readiness_action="actions", action_id="", target="44")),
            0,
        )
        service.get_candidate.return_value = None
        self.assertEqual(
            _cmd_readiness_action(SimpleNamespace(readiness_action="action-info", action_id="missing", target="44")),
            1,
        )
        output_json.assert_called_with({"error": "not_found", "action_id": "missing"})
        self.assertEqual(
            _cmd_readiness_action(SimpleNamespace(readiness_action="bad", action_id="", target="44")),
            1,
        )
        output_json.assert_called_with({"error": "unknown_readiness_action", "action": "bad"})


class TestCliActionCenterPresentationBranches(unittest.TestCase):
    @staticmethod
    def _policy():
        return SimpleNamespace(
            reason_code="preflight_ok",
            explanation="Safe to continue",
            to_dict=lambda: {"allowed": True, "reason_code": "preflight_ok"},
        )

    @classmethod
    def _plan(cls):
        return SimpleNamespace(
            plan_id="plan-1",
            action_id="dnf-clean-all",
            state="needs_review",
            preview=["dnf", "clean", "all"],
            expires_at=2000.0,
            policy_decision=cls._policy(),
            risk_level="medium",
            privileged=True,
            recovery_guidance="Refresh metadata",
            to_dict=lambda: {"plan_id": "plan-1", "state": "needs_review"},
        )

    @classmethod
    def _run(cls, state="verifying"):
        return SimpleNamespace(
            run_id="run-1",
            plan_id="plan-1",
            action_id="dnf-clean-all",
            state=state,
            recovery_status="manual",
            to_dict=lambda: {"run_id": "run-1", "action_id": "dnf-clean-all", "state": state},
        )

    @patch("cli.main._print")
    @patch("cli.main._json_output", False)
    @patch("core.actions.ActionCenterOrchestrator")
    def test_plan_show_apply_and_verify_text(self, orchestrator_cls, print_fn):
        from cli.main import cmd_action_center

        orchestrator = orchestrator_cls.return_value
        plan = self._plan()
        orchestrator.plan.return_value = plan
        orchestrator.get_plan.return_value = plan
        orchestrator.apply.return_value = self._run("failed")
        orchestrator.verify.return_value = self._run("verification_failed")

        self.assertEqual(
            cmd_action_center(SimpleNamespace(action="plan", action_id="dnf-clean-all", target="44", service=None)),
            0,
        )
        self.assertEqual(cmd_action_center(SimpleNamespace(action="show", action_id="plan-1", target="44")), 0)
        self.assertEqual(
            cmd_action_center(
                SimpleNamespace(action="apply", action_id="plan-1", target="44", confirm=True, accept_no_rollback=True)
            ),
            1,
        )
        self.assertEqual(cmd_action_center(SimpleNamespace(action="verify", action_id="run-1", target="44")), 1)
        print_fn.assert_any_call("Preview: dnf clean all")
        print_fn.assert_any_call("Recovery: Refresh metadata")

    @patch("cli.main._print")
    @patch("cli.main._json_output", False)
    @patch("core.actions.ActionCenterOrchestrator")
    def test_orchestrator_errors_are_presented(self, orchestrator_cls, print_fn):
        from cli.main import cmd_action_center
        from core.actions import ActionCenterBusyError, ActionCenterError, ActionPlanRejectedError, PolicyDecision

        args = SimpleNamespace(action="plan", action_id="dnf-clean-all", target="44", service=None)
        orchestrator_cls.return_value.plan.side_effect = ActionPlanRejectedError(
            PolicyDecision(False, "blocked", "Policy blocked this action")
        )
        self.assertEqual(cmd_action_center(args), 1)
        print_fn.assert_called_with("Action blocked: blocked - Policy blocked this action")

        orchestrator_cls.return_value.plan.side_effect = ActionCenterBusyError("Another action is running")
        self.assertEqual(cmd_action_center(args), 1)
        print_fn.assert_called_with("Another action is running")

        orchestrator_cls.return_value.plan.side_effect = ActionCenterError("Plan failed")
        self.assertEqual(cmd_action_center(args), 1)
        print_fn.assert_called_with("Plan failed")

    @patch("cli.commands.readiness_commands._print_action_result", return_value=0)
    @patch("cli.main._print")
    @patch("cli.main._json_output", False)
    @patch("core.actions.ActionRunStore")
    @patch("core.actions.ActionPlanStore")
    @patch("core.actions.ActionCenterService")
    def test_list_recommendations_preview_history_and_unknown_text(
        self,
        service_cls,
        plan_store_cls,
        run_store_cls,
        print_fn,
        print_result,
    ):
        from cli.main import cmd_action_center

        candidate = SimpleNamespace(
            id="dnf-clean-all",
            title="Clean metadata",
            state="ready",
            risk_level="medium",
            description="Reclaims space",
            command_preview=["dnf", "clean", "all"],
            rollback_hint="Refresh metadata",
            to_dict=lambda: {"id": "dnf-clean-all"},
        )
        recommendation = SimpleNamespace(
            id="health-trend",
            title="Review health trend",
            risk_level="low",
            why_this_matters="Health changed",
            safe_next_step="Open timeline",
            to_dict=lambda: {"id": "health-trend"},
        )
        service = service_cls.return_value
        service.candidates_from_readiness.return_value = [candidate]
        service.recommendations_from_timeline.return_value = [recommendation]
        service.preview.return_value = object()
        service.recent_history.return_value = [{"action": "legacy"}]
        plan_store_cls.return_value.list.return_value = [SimpleNamespace(to_dict=lambda: {"plan_id": "plan-1"})]
        run_store_cls.return_value.list.return_value = [self._run("succeeded")]

        self.assertEqual(cmd_action_center(SimpleNamespace(action="list", target="44")), 0)
        print_fn.assert_any_call("  Rollback: Refresh metadata")
        self.assertEqual(cmd_action_center(SimpleNamespace(action="recommendations", target="44", limit=5)), 0)
        print_fn.assert_any_call("  Safe next step: Open timeline")
        self.assertEqual(cmd_action_center(SimpleNamespace(action="preview", target="44", action_id="dnf-clean-all")), 0)
        self.assertEqual(cmd_action_center(SimpleNamespace(action="history", target="44", limit=5)), 0)
        print_fn.assert_any_call("run-1: dnf-clean-all [succeeded]")
        self.assertEqual(cmd_action_center(SimpleNamespace(action="bad", target="44")), 1)
        print_fn.assert_called_with("Unknown Action Center command: bad")
        print_result.assert_called_once()

    @patch("cli.main._output_json")
    @patch("cli.main._json_output", True)
    @patch("core.actions.ActionRunStore")
    @patch("core.actions.ActionPlanStore")
    @patch("core.actions.ActionCenterService")
    def test_list_missing_preview_empty_history_and_unknown_json(
        self,
        service_cls,
        plan_store_cls,
        run_store_cls,
        output_json,
    ):
        from cli.main import cmd_action_center

        service_cls.return_value.candidates_from_readiness.return_value = []
        service_cls.return_value.recent_history.return_value = []
        plan_store_cls.return_value.list.return_value = []
        run_store_cls.return_value.list.return_value = []

        self.assertEqual(cmd_action_center(SimpleNamespace(action="list", target="44")), 0)
        self.assertEqual(cmd_action_center(SimpleNamespace(action="preview", target="44", action_id="missing")), 1)
        output_json.assert_called_with({"schema_version": 3, "error": "not_found", "action_id": "missing"})
        self.assertEqual(cmd_action_center(SimpleNamespace(action="history", target="44", limit=5)), 0)
        self.assertEqual(cmd_action_center(SimpleNamespace(action="bad", target="44")), 1)
        output_json.assert_called_with({"schema_version": 3, "error": "unknown_action_center_command", "action": "bad"})


if __name__ == "__main__":
    unittest.main()
