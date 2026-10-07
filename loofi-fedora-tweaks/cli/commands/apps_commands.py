"""CLI handlers for curated application management."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable, cast

from core.actions import ActionCatalog, ActionCenterOrchestrator
from core.actions.catalog import SystemActionRuntime
from core.actions.operation_controller import OperationController
from services.software.installed_applications import InstalledApplicationService, installation_flag, validate_ref
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

    if action in {"details", "unused", "cleanup"}:
        from services.software.flatpak_maintenance import FlatpakMaintenanceService, UnusedSnapshot, REF_PATTERN

        def report_metadata_error(message: str) -> int:
            if json_output:
                output_json({"available": False, "status": "unavailable", "error": message})
            else:
                print_fn(message)
            return 1

        try:
            installation_flag(args.installation)
            if action == "details" and not validate_ref(args.ref):
                return report_metadata_error("Select one full installed application ref.")
            if action == "cleanup":
                refs = getattr(args, "refs", ())
                if (not refs or len(refs) > 256 or len(refs) != len(set(refs))
                        or any(not isinstance(ref, str) or not REF_PATTERN.fullmatch(ref) or not ref.startswith("runtime/") for ref in refs)):
                    return report_metadata_error("Select one or more distinct full runtime refs for cleanup.")
        except (TypeError, ValueError):
            return report_metadata_error("Select a valid Flatpak installation identifier.")
        maintenance = FlatpakMaintenanceService()
        try:
            result = maintenance.details(args.ref, args.installation) if action == "details" else maintenance.unused(args.installation)
        except (OSError, RuntimeError, TypeError, ValueError):
            return report_metadata_error("Local Flatpak metadata could not be read.")
        if action != "cleanup" or not result.available:
            if json_output:
                output_json(result.to_dict())
            else:
                for key, value in result.to_dict().items():
                    print_fn(f"{key}: {value}")
                if action == "details" and result.available:
                    print_fn("No local EOL warning does not guarantee continued support.")
            return 0 if result.available else 1
        parameters = {"installation": args.installation, "refs": args.refs, "snapshot_digest": cast(UnusedSnapshot, result).digest}
        controller = OperationController(orchestrator=ActionCenterOrchestrator(catalog=ActionCatalog(), runtime=runtime))
        try:
            ticket = controller.prepare("remove-unused-flatpaks", parameters)
        except (OSError, RuntimeError, TypeError, ValueError):
            return report_metadata_error("Runtime cleanup could not be prepared. Inspect the installation again.")
        if not ticket.plan.policy_decision.allowed:
            if json_output:
                output_json(ticket.plan.to_dict())
            else:
                print_fn(ticket.plan.policy_decision.explanation)
            return 1
        if dry_run or not getattr(args, "yes", False):
            if json_output:
                output_json(ticket.plan.to_dict())
            else:
                print_fn(f"Review runtimes in {args.installation}: {', '.join(args.refs)}")
                if args.installation != "user":
                    print_fn("Shared installation: other users' private app inventories have not been inspected.")
                print_fn("Reported sizes do not predict freed space. App data is preserved. Recovery is manual reinstallation; there is no automatic rollback. Pass --yes to accept and confirm exact runtime removal.")
            return 0
        try:
            confirmed = controller.confirm(ticket, confirmed=True, accept_no_rollback=True)
        except (OSError, RuntimeError, TypeError, ValueError):
            return report_metadata_error("Runtime cleanup review could not be confirmed. Inspect the installation again.")
        if confirmed.status != "prepared":
            if json_output:
                output_json(confirmed.to_dict())
            else:
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

    if action == "permissions":
        service = InstalledApplicationService()
        inventory = service.flatpaks()

        def report_permission_error(message: str) -> None:
            if json_output:
                output_json({
                    "schema": "loofi.flatpak-permissions/v1",
                    "status": "unavailable",
                    "ref": args.ref,
                    "installation": args.installation,
                    "permissions": [],
                    "error": message,
                })
            else:
                print_fn(message)

        if inventory.unknown_sources:
            report_permission_error("Flatpak installation inventory could not be read.")
            return 1
        selected = next((app for app in inventory.applications
                         if app.ref == args.ref and app.installation == args.installation), None)
        if selected is None:
            report_permission_error("The selected Flatpak ref is not installed in this installation.")
            return 1
        try:
            permissions = service.permissions(selected)
        except (OSError, RuntimeError, TypeError, ValueError):
            report_permission_error("Permissions could not be read from this installation.")
            return 1
        if json_output:
            output_json(permissions.to_dict())
        else:
            print_fn(f"Permissions requested by {permissions.name}")
            print_fn(f"Ref: {permissions.ref}")
            print_fn(f"Installation: {permissions.installation}")
            for item in permissions.permissions:
                value = "[hidden]" if item.category.lower() == "environment" else item.value
                print_fn(f"[{item.category}] {item.key}: {value}")
            if not permissions.permissions:
                print_fn("No permissions were reported by the app metadata.")
            print_fn("User overrides and desktop portals can change actual access.")
        return 0

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
