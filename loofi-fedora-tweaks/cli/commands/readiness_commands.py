"""State, readiness, and Action Center CLI handlers."""

from __future__ import annotations

import json as json_module
from typing import Any, Dict, List, cast

from core.fedora_release_policy import FEDORA_RELEASE_POLICY


def _main_module():
    from cli import main

    return main


def _print(text):
    return _main_module()._print(text)


def _output_json(data):
    return _main_module()._output_json(data)


def _json_mode() -> bool:
    return bool(_main_module()._json_output)


def _timeout() -> int:
    return int(_main_module()._operation_timeout)


def cmd_state(args):
    """Read-only state diagnostics and explicit backup/restore flows."""
    from pathlib import Path

    from core.state import StateArchiveService, StateDoctor

    if args.state_action == "doctor":
        payload = StateDoctor().run()
    elif args.state_action == "backup":
        payload = StateArchiveService().backup(Path(args.output).expanduser())
    elif args.state_action == "restore":
        service = StateArchiveService()
        archive = Path(args.archive).expanduser()
        if args.restore_action == "plan":
            payload = service.plan_restore(archive)
        elif not args.plan_id:
            _print("--plan-id is required for restore apply")
            return 2
        else:
            payload = service.apply_restore(archive, args.plan_id)
    else:
        _print("Choose doctor, backup, or restore")
        return 2
    _output_json(payload)
    return 1 if payload.get("status") == "error" else 0


def _print_readiness_report(report, *, advanced: bool) -> int:
    """Print a readiness report in CLI text or JSON mode."""
    if _json_mode():
        _output_json(report.to_dict(advanced=advanced))
        return 0 if report.status in {"ready", "preview"} else 1

    _print("═══════════════════════════════════════════")
    _print(f"   {report.target} Readiness")
    _print("═══════════════════════════════════════════")
    _print(f"\nScore: {report.score}/100")
    _print(report.summary)
    for check in report.checks:
        marker = "OK" if check.status == "pass" else check.status.upper()
        _print(f"\n[{marker}] {check.title}")
        _print(f"  {check.summary}")
        _print(f"  {check.beginner_guidance}")
        if check.recommendation:
            _print(f"  Recommendation: {check.recommendation.title}")
        if advanced:
            if check.command_preview:
                _print(f"  Command: {' '.join(check.command_preview)}")
            if check.advanced_detail:
                _print(f"  Detail: {check.advanced_detail[:600]}")
    return 0 if report.status in {"ready", "preview"} else 1


def _print_release_plan(report) -> int:
    """Print a guided release plan in CLI text or JSON mode."""
    from core.diagnostics.release_readiness import ReleaseReadiness

    plan = cast(Dict[str, Any], ReleaseReadiness.build_release_plan(report))
    if _json_mode():
        _output_json(plan)
        return 0

    _print("═══════════════════════════════════════════")
    _print(f"   {report.target} Upgrade Plan")
    _print("═══════════════════════════════════════════")
    _print(f"\nScore: {report.score}/100")
    _print(str(plan["summary"]))
    _print(f"Next action: {plan['next_action']}")

    changes = cast(Dict[str, Any], plan.get("target_changes", {}))
    important = cast(List[Dict[str, Any]], changes.get("important_changes", []))
    risks = cast(List[Dict[str, Any]], changes.get("known_risks", []))
    if important:
        _print("\nWhat changed:")
        for change in important:
            _print(f"- {change.get('title')}: {change.get('summary')}")
    if risks:
        _print("\nKnown risks:")
        for risk in risks:
            _print(f"- {risk.get('title')}: {risk.get('summary')}")

    attention = cast(List[Dict[str, Any]], plan.get("attention", []))
    if attention:
        _print("\nNeeds review:")
        for check in attention:
            _print(f"- {check.get('id')}: {check.get('summary')}")
    return 0


def cmd_readiness(args):
    """Run release readiness diagnostics."""
    from core.diagnostics.release_readiness import ReleaseReadiness

    readiness_action = getattr(args, "readiness_action", None)
    if readiness_action:
        if isinstance(readiness_action, str):
            return _cmd_readiness_action(args)

    target = getattr(args, "target", FEDORA_RELEASE_POLICY.stable_target)
    report = ReleaseReadiness.run(target)
    return _print_readiness_report(report, advanced=getattr(args, "advanced", False))


def cmd_fedora44_readiness(args):
    """Run Fedora KDE 44 readiness diagnostics (compatibility alias)."""
    from core.diagnostics.release_readiness import ReleaseReadiness

    report = ReleaseReadiness.run(FEDORA_RELEASE_POLICY.stable_target)
    return _print_readiness_report(report, advanced=getattr(args, "advanced", False))


def _print_action_result(result) -> int:
    """Print an action result in text or JSON form."""
    payload = result.to_dict()
    if _json_mode():
        _output_json(payload)
    else:
        status = "OK" if result.success else "FAILED"
        _print(f"[{status}] {result.message}")
        candidate = (result.data or {}).get("candidate") if result.data else None
        plan_id = (result.data or {}).get("plan_id") if result.data else None
        definition_id = (result.data or {}).get("definition_id") if result.data else None
        if plan_id:
            _print(f"Plan {plan_id}: {definition_id} [review required]")
            _print(f"Next: {(result.data or {}).get('next_action')}")
        if candidate:
            command_preview = candidate.get("command_preview") or []
            if command_preview:
                _print(f"Command preview: {' '.join(command_preview)}")
            _print(f"Risk: {candidate.get('risk_level')}  Privileged: {candidate.get('privileged')}  Manual only: {candidate.get('manual_only')}")
            if candidate.get("revert_hint"):
                _print(f"Rollback: {candidate.get('revert_hint')}")
    return 0 if result.success else 1


def _cmd_readiness_action(args) -> int:
    """Handle nested readiness action commands."""
    from core.diagnostics.readiness_actions import ReadinessActionService

    target = getattr(args, "target", FEDORA_RELEASE_POLICY.stable_target)
    action = getattr(args, "readiness_action", "")
    action_id = getattr(args, "action_id", "")

    if action == "actions":
        plan = ReadinessActionService.build_plan(target)
        if _json_mode():
            _output_json(plan.to_dict())
        else:
            _print(f"{plan.target} Action Inbox")
            if not plan.candidates:
                _print("No readiness actions are currently available.")
            for plan_candidate in plan.candidates:
                mode = "manual" if plan_candidate.manual_only else "executable"
                _print(f"- {plan_candidate.id}: {plan_candidate.title} [{plan_candidate.risk_level}, {mode}]")
                _print(f"  {plan_candidate.explanation}")
                if plan_candidate.command_preview:
                    _print(f"  Preview: {' '.join(plan_candidate.command_preview)}")
        return 0

    if action == "plan":
        from core.diagnostics.release_readiness import ReleaseReadiness

        report = ReleaseReadiness.run(target, mode="upgrade-plan")
        return _print_release_plan(report)

    if action == "explain":
        from core.diagnostics.release_readiness import ReleaseReadiness

        explanation = ReleaseReadiness.explain_check(action_id, target, mode="upgrade-plan")
        if explanation is None:
            if _json_mode():
                _output_json({"error": "not_found", "check_id": action_id})
            else:
                _print(f"Readiness check not found: {action_id}")
            return 1
        if _json_mode():
            _output_json(explanation)
        else:
            check = cast(Dict[str, Any], explanation["check"])
            _print(f"{check['title']} ({check['id']})")
            _print(check["summary"])
            _print(check["beginner_guidance"])
            if check.get("command_preview"):
                _print(f"Command: {' '.join(check['command_preview'])}")
            if check.get("advanced_detail"):
                _print(f"Detail: {str(check['advanced_detail'])[:1000]}")
        return 0

    if action == "export":
        from core.export.support_bundle import SupportBundleWriter

        path = getattr(args, "path", None) or f"loofi-readiness-{target}.json"
        if _json_mode():
            _output_json(SupportBundleWriter.generate_bundle(target=target))
            return 0
        SupportBundleWriter.save_json(path, target=target)
        _print(f"Exported readiness support bundle: {path}")
        return 0

    if action == "action-info":
        candidate = ReadinessActionService.get_candidate(action_id, target)
        if candidate is None:
            if _json_mode():
                _output_json({"error": "not_found", "action_id": action_id})
            else:
                _print(f"Readiness action not found: {action_id}")
            return 1
        if _json_mode():
            _output_json(candidate.to_dict())
        else:
            _print(f"{candidate.title} ({candidate.id})")
            _print(candidate.explanation)
            _print(f"Related check: {candidate.related_check_id}")
            _print(f"Risk: {candidate.risk_level}")
            _print(f"Privileged: {candidate.privileged}")
            _print(f"Manual only: {candidate.manual_only}")
            if candidate.command_preview:
                _print(f"Command preview: {' '.join(candidate.command_preview)}")
            if candidate.revert_hint:
                _print(f"Rollback: {candidate.revert_hint}")
            if candidate.verification_command:
                _print(f"Verify: {' '.join(candidate.verification_command)}")
            if candidate.docs_link:
                _print(f"Docs: {candidate.docs_link}")
        return 0

    if action == "action-preview":
        return _print_action_result(ReadinessActionService.preview(action_id, target))

    if action == "action-run":
        result = ReadinessActionService.run(
            action_id,
            target_key=target,
            confirm=getattr(args, "confirm", False),
        )
        return _print_action_result(result)

    if action == "action-verify":
        return _print_action_result(ReadinessActionService.verify(action_id, target))

    if _json_mode():
        _output_json({"error": "unknown_readiness_action", "action": action})
    else:
        _print(f"Unknown readiness action command: {action}")
    return 1


def cmd_action_center(args) -> int:
    """Plan, apply, verify, and inspect Action Center maintenance."""
    from core.actions import (
        ActionCatalog,
        ActionCenterBusyError,
        ActionCenterError,
        ActionCenterOrchestrator,
        ActionCenterService,
        ActionPlanRejectedError,
        ActionPlanStore,
        ActionRunStore,
    )

    target = getattr(args, "target", FEDORA_RELEASE_POLICY.stable_target)
    action = getattr(args, "action", "list")

    def emit(payload: Dict[str, Any], lines: List[str]) -> None:
        if _json_mode():
            _output_json(payload)
        else:
            for line in lines:
                _print(line)

    if action in {"plan", "show", "apply", "verify"}:
        identifier = str(getattr(args, "action_id", "") or "")
        catalog = ActionCatalog()
        orchestrator = ActionCenterOrchestrator(catalog=catalog)
        try:
            if action == "plan":
                definition = catalog.get(identifier)
                if definition is None:
                    payload = {
                        "schema_version": 4,
                        "error": "unknown_action_definition",
                        "definition_id": identifier,
                        "auto_apply": False,
                    }
                    emit(payload, [f"Unknown Action Center definition: {identifier}"])
                    return 1
                parameters = {}
                service_unit = getattr(args, "service", None)
                if service_unit:
                    parameters["service"] = service_unit
                for argument, parameter in (
                    ("package_id", "package_id"),
                    ("source", "source"),
                    ("backend", "backend"),
                    ("description", "description"),
                    ("days", "days"),
                ):
                    value = getattr(args, argument, None)
                    expected_type = int if argument == "days" else str
                    if isinstance(value, expected_type) and not isinstance(value, bool) and value != "":
                        parameters[parameter] = value
                from core.actions.catalog import validate_parameters

                parameter_decision = validate_parameters(definition, parameters)
                if not parameter_decision.allowed:
                    payload = {
                        "schema_version": 4,
                        "error": "invalid_action_parameters",
                        "definition_id": identifier,
                        "reason_code": parameter_decision.reason_code,
                        "message": parameter_decision.explanation,
                        "auto_apply": False,
                    }
                    emit(payload, [f"Invalid parameters for {identifier}: {parameter_decision.explanation}"])
                    return 1
                plan = orchestrator.plan(identifier, parameters, target=target)
                payload = {
                    "schema_version": 3,
                    "plan": plan.to_dict(),
                    "policy_decision": plan.policy_decision.to_dict(),
                }
                emit(
                    payload,
                    [
                        f"Plan {plan.plan_id}: {plan.action_id} [{plan.state}]",
                        f"Policy: {plan.policy_decision.reason_code} - {plan.policy_decision.explanation}",
                        f"Preview: {' '.join(plan.preview) if plan.preview else 'manual-only'}",
                        f"Expires: {plan.expires_at}",
                    ],
                )
                return 0 if plan.state != "blocked" else 1

            if action == "show":
                plan = orchestrator.get_plan(identifier)
                payload = {
                    "schema_version": 3,
                    "plan": plan.to_dict(),
                    "policy_decision": plan.policy_decision.to_dict(),
                }
                emit(
                    payload,
                    [
                        f"Plan {plan.plan_id}: {plan.action_id} [{plan.state}]",
                        f"Risk: {plan.risk_level}; privileged: {plan.privileged}",
                        f"Policy: {plan.policy_decision.reason_code} - {plan.policy_decision.explanation}",
                        f"Preview: {' '.join(plan.preview) if plan.preview else 'manual-only'}",
                        f"Recovery: {plan.recovery_guidance}",
                    ],
                )
                return 0

            if action == "apply":
                plan = orchestrator.get_plan(identifier)
                run = orchestrator.apply(
                    identifier,
                    confirmed=bool(getattr(args, "confirm", False)),
                    accept_no_rollback=bool(getattr(args, "accept_no_rollback", False)),
                    timeout=_timeout(),
                )
                payload = {
                    "schema_version": 3,
                    "run": run.to_dict(),
                    "policy_decision": plan.policy_decision.to_dict(),
                }
                emit(
                    payload,
                    [
                        f"Run {run.run_id}: {run.action_id} [{run.state}]",
                        "Execution recorded. Run the separate verify command if state is verifying.",
                        f"Recovery: {run.recovery_status}",
                    ],
                )
                return 0 if run.state == "verifying" else 1

            run = orchestrator.verify(identifier)
            plan = orchestrator.get_plan(run.plan_id)
            payload = {
                "schema_version": 3,
                "run": run.to_dict(),
                "policy_decision": plan.policy_decision.to_dict(),
            }
            emit(
                payload,
                [
                    f"Run {run.run_id}: {run.action_id} [{run.state}]",
                    f"Recovery: {run.recovery_status}",
                ],
            )
            return 0 if run.state in {"succeeded", "awaiting_reboot"} else 1
        except ActionPlanRejectedError as exc:
            payload = {
                "schema_version": 3,
                "error": "action_plan_rejected",
                "policy_decision": exc.decision.to_dict(),
            }
            emit(payload, [f"Action blocked: {exc.decision.reason_code} - {exc.decision.explanation}"])
            return 1
        except ActionCenterBusyError as exc:
            payload = {"schema_version": 3, "error": "action_center_busy", "message": str(exc)}
            emit(payload, [str(exc)])
            return 1
        except ActionCenterError as exc:
            payload = {"schema_version": 3, "error": "action_center_error", "message": str(exc)}
            emit(payload, [str(exc)])
            return 1

    service = ActionCenterService()
    candidates = service.candidates_from_readiness(target)

    if action == "list":
        payload = {"schema_version": 3, "target": target, "candidates": [item.to_dict() for item in candidates]}
        if _json_mode():
            _output_json(payload)
            return 0
        _print(f"{target} Action Center")
        if not candidates:
            _print("No action candidates are currently available.")
        for item in candidates:
            _print(f"- {item.id}: {item.title} [{item.state}, {item.risk_level}]")
            _print(f"  {item.description}")
            if item.command_preview:
                _print(f"  Preview: {' '.join(item.command_preview)}")
            if item.rollback_hint:
                _print(f"  Rollback: {item.rollback_hint}")
        return 0

    if action == "recommendations":
        recommendations = service.recommendations_from_timeline(limit=getattr(args, "limit", 25))
        payload = {"schema_version": 3, "recommendations": [item.to_dict() for item in recommendations]}
        if _json_mode():
            _output_json(payload)
        else:
            if not recommendations:
                _print("No Action Center recommendations from the health timeline.")
            for item in recommendations:
                _print(f"- {item.id}: {item.title} [{item.risk_level}]")
                _print(f"  Why: {item.why_this_matters}")
                _print(f"  Safe next step: {item.safe_next_step}")
        return 0

    if action == "preview":
        action_id = getattr(args, "action_id", "")
        preview_item = next((candidate for candidate in candidates if candidate.id == action_id), None)
        if preview_item is None:
            if _json_mode():
                _output_json({"schema_version": 3, "error": "not_found", "action_id": action_id})
            else:
                _print(f"Action Center item not found: {action_id}")
            return 1
        return _print_action_result(service.preview(preview_item))

    if action == "history":
        limit = getattr(args, "limit", 25)
        legacy_history = service.recent_history(limit=limit)
        plan_history = [plan.to_dict() for plan in ActionPlanStore().list(limit=min(limit, 50))]
        run_history = [run.to_dict() for run in ActionRunStore().list(limit=min(limit, 100))]
        payload = {
            "schema_version": 3,
            "history": legacy_history,
            "plans": plan_history,
            "runs": run_history,
        }
        if _json_mode():
            _output_json(payload)
        else:
            if not legacy_history and not run_history:
                _print("No Action Center history recorded.")
            for entry in legacy_history:
                _print(json_module.dumps(entry, default=str))
            for run_entry in run_history:
                _print(f"{run_entry['run_id']}: {run_entry['action_id']} [{run_entry['state']}]")
        return 0

    if _json_mode():
        _output_json({"schema_version": 3, "error": "unknown_action_center_command", "action": action})
    else:
        _print(f"Unknown Action Center command: {action}")
    return 1
