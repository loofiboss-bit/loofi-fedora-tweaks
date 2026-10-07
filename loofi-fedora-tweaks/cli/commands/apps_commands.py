"""CLI handlers for curated application management."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable

from core.actions import ActionCatalog, ActionCenterOrchestrator
from core.actions.catalog import SystemActionRuntime
from core.actions.operation_controller import OperationController
from services.software.installed_applications import InstalledApplicationService
from core.executor.command_facade import CommandFacade
from core.platform import detect_platform_profile
from core.tasks.applications import ApplicationCatalog, ApplicationContext
from core.tasks.catalog import TaskContext


def handle_apps(
    args: Any,
    json_output: bool,
    output_json: Callable[[Any], None],
    print_fn: Callable[[str], None],
    *,
    dry_run: bool = False,
) -> int:
    action = getattr(args, "apps_action", "list") or "list"
    profile = detect_platform_profile()
    runtime = SystemActionRuntime(CommandFacade())
    task_context = TaskContext.from_platform_profile(profile)
    app_context = ApplicationContext.from_task_context(task_context)
    catalog = ApplicationCatalog()

    if action in {"list", "installed"}:
        inventory = InstalledApplicationService().snapshot()
        app_context = replace(app_context, installed_ids=inventory.installed_ids, unknown_sources=inventory.unknown_sources)
        if action == "installed":
            if json_output:
                output_json(inventory.to_dict())
            else:
                for installed_app in inventory.applications:
                    print_fn(f"{installed_app.name} · {installed_app.source} · {installed_app.installation} · {installed_app.version} · {installed_app.size} · {installed_app.ref}")
                for error in inventory.errors:
                    print_fn(error)
            return 1 if inventory.errors else 0

    if action == "remove":
        controller = OperationController(orchestrator=ActionCenterOrchestrator(catalog=ActionCatalog(), runtime=runtime))
        ticket = controller.prepare("remove-installed-flatpak", {"ref": args.ref, "installation": args.installation})
        if not ticket.plan.policy_decision.allowed:
            print_fn(ticket.plan.policy_decision.explanation)
            return 1
        if dry_run or not getattr(args, "yes", False):
            if json_output:
                output_json(ticket.plan.to_dict())
            else:
                print_fn(f"Remove {args.ref} from {args.installation}. Application data is preserved.")
                print_fn("Pass --yes to confirm execution.")
            return 0
        confirmed = controller.confirm(ticket, confirmed=True, accept_no_rollback=True)
        if confirmed.status != "prepared":
            print_fn(confirmed.message)
            return 1
        outcome = controller.run(confirmed)
        if outcome.status == "verifying":
            outcome = controller.verify(outcome)
        if json_output:
            output_json(outcome.to_dict())
        else:
            print_fn(outcome.message)
        return 0 if outcome.status == "succeeded" else 1

    if action == "list":
        category_filter = getattr(args, "category", None)
        apps_with_eligibility = catalog.search(category=category_filter, context=app_context)
        if json_output:
            output_json({
                "schema_version": 1,
                "inventory_errors": list(inventory.errors),
                "applications": [
                    {
                        "id": app.id,
                        "name": app.name,
                        "category": app.category,
                        "source": app.source,
                        "source_label": app.source_label,
                        "package_id": app.package_id,
                        "description": app.description,
                        "state": elig.state,
                        "installed": elig.installed,
                        "selectable": elig.selectable,
                    }
                    for app, elig in apps_with_eligibility
                ],
            })
        else:
            print_fn(f"{'ID':<16} {'NAME':<24} {'CATEGORY':<14} {'SOURCE':<10} {'STATUS'}")
            print_fn("-" * 75)
            for app, elig in apps_with_eligibility:
                status_label = "Installed" if elig.installed else elig.state.capitalize()
                print_fn(f"{app.id:<16} {app.name[:23]:<24} {app.category:<14} {app.source:<10} {status_label}")
        return 0

    if action == "install":
        app_id = getattr(args, "app_id", "").strip()
        record = catalog.get(app_id)
        if record is None:
            print_fn(f"Unknown application: {app_id}")
            return 1
        action_cat = ActionCatalog()
        orchestrator = ActionCenterOrchestrator(catalog=action_cat, runtime=runtime)
        plan = orchestrator.plan("install-application", {
            "source": record.source,
            "package_id": record.package_id,
        })
        if not plan.policy_decision.allowed:
            print_fn(f"Cannot install {record.name}: {plan.policy_decision.explanation}")
            return 1
        if dry_run:
            print_fn(f"[dry-run] Would install {record.name} ({record.source_label})")
            return 0
        if not getattr(args, "yes", False):
            print_fn(f"Plan: Install '{record.name}' via {record.source_label}")
            print_fn(f"Package: {record.package_id}")
            print_fn("Pass --yes to confirm execution.")
            return 0
        run = orchestrator.execute(plan)
        if run.state == "succeeded":
            print_fn(f"Successfully installed {record.name}.")
            return 0
        print_fn(f"Failed to install {record.name}: {run.error_message}")
        return 1

    return 0
