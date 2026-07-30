"""Shared CLI handoff to closed Action Center definitions."""

from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

from core.actions import ActionCatalog, ActionCenterOrchestrator
from core.actions.catalog import validate_parameters
from core.actions.public_operations import public_operation


def create_public_plans(
    requests: Sequence[tuple[str, Mapping[str, Any]]],
    *,
    json_output: bool,
    output_json: Callable[[Any], Any],
    print_fn: Callable[[Any], Any],
) -> int:
    """Create review plans for classified public operations without applying."""
    catalog = ActionCatalog()
    orchestrator = ActionCenterOrchestrator(catalog=catalog)
    plans = []
    summaries = []
    for operation_id, parameters in requests:
        operation = public_operation(operation_id)
        action_ids = operation.action_definition_ids
        if len(action_ids) != 1:
            raise ValueError(f"{operation_id} requires an exact Action Center definition.")
        action_id = action_ids[0]
        definition = catalog.get(action_id)
        if definition is None:
            raise ValueError(f"Unknown Action Center definition: {action_id}")
        parameter_decision = validate_parameters(definition, parameters)
        if not parameter_decision.allowed:
            payload = {
                "schema_version": 4,
                "error": "invalid_action_parameters",
                "operation_id": operation_id,
                "definition_id": action_id,
                "reason_code": parameter_decision.reason_code,
                "message": parameter_decision.explanation,
                "auto_apply": False,
            }
            if json_output:
                output_json(payload)
            else:
                print_fn(f"Invalid parameters for {action_id}: {parameter_decision.explanation}")
            return 1
        plan = orchestrator.plan(action_id, dict(parameters))
        plans.append(plan)
        summaries.append(
            {
                "operation_id": operation_id,
                "classification": operation.classification,
                "plan_id": plan.plan_id,
                "state": plan.state,
                "definition_id": plan.action_id,
                "review_required": True,
                "auto_apply": False,
                "next_action": (
                    f"loofi-fedora-tweaks --cli action-center apply {plan.plan_id} --confirm"
                    if plan.state != "blocked"
                    else operation.recovery_guidance
                ),
                "compatibility_alias": operation.compatibility_alias,
            }
        )

    payload = {
        "schema_version": 4,
        "plans": [plan.to_dict() for plan in plans],
        "plan_summaries": summaries,
        "review_required": True,
        "auto_apply": False,
    }
    if json_output:
        output_json(payload)
    else:
        for plan, summary in zip(plans, summaries):
            print_fn(f"Plan {plan.plan_id}: {plan.action_id} [{plan.state}]")
            print_fn(f"  {plan.policy_decision.explanation}")
            print_fn(f"  Next: {summary['next_action']}")
    return 0


def manual_guidance(
    operation_id: str,
    message: str,
    *,
    json_output: bool,
    output_json: Callable[[Any], Any],
    print_fn: Callable[[Any], Any],
) -> int:
    """Return stable manual-only guidance without persisting an open plan."""
    operation = public_operation(operation_id)
    payload = {
        "schema_version": 4,
        "operation_id": operation_id,
        "classification": "manual_only",
        "message": message,
        "review_required": True,
        "auto_apply": False,
        "next_action": operation.recovery_guidance,
    }
    if json_output:
        output_json(payload)
    else:
        print_fn(message)
        print_fn(f"Next: {operation.recovery_guidance}")
    return 0
