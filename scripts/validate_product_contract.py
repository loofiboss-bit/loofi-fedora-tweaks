#!/usr/bin/env python3
"""Version-neutral gate for product trust-boundary and catalog contracts."""

from __future__ import annotations

import ast
import argparse
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "loofi-fedora-tweaks"
sys.path.insert(0, str(SOURCE))

import core  # noqa: E402
import services  # noqa: E402

from core.execution_policy import classify_command, presentation_operation_class  # noqa: E402
from core.product_catalog import product_catalog, validate_product_catalog  # noqa: E402
from core.actions.public_operations import validate_public_operation_inventory  # noqa: E402
from core.tasks import validate_task_catalog  # noqa: E402
from core.catalog_records.utility import (  # noqa: E402
    TASK_ROUTE_RECORDS,
    TASK_ROUTE_REDIRECTS,
    action_classifications,
    validate_route_classifications,
)
from core.navigation.manifest import all_routes  # noqa: E402


def _action_definitions() -> list[object]:
    """Load the pure catalog without requiring PyQt in the dependency-free CI gate."""
    if "core.actions" in sys.modules:
        from core.actions.catalog import ActionCatalog

        return list(ActionCatalog().list())

    actions_package = types.ModuleType("core.actions")
    actions_package.__path__ = [str(SOURCE / "core" / "actions")]
    actions_package.__package__ = "core"
    system_package = types.ModuleType("services.system")
    system_package.__path__ = [str(SOURCE / "services" / "system")]
    system_package.__package__ = "services"
    sys.modules["core.actions"] = actions_package
    sys.modules["services.system"] = system_package
    try:
        from core.actions.catalog import ActionCatalog

        # Validate the same filtered live catalog that the application exposes.
        # Historical compatibility definitions are intentionally not part of
        # the v27 public Action Center surface.
        return list(ActionCatalog().list())
    finally:
        sys.modules.pop("core.actions", None)
        sys.modules.pop("services.system", None)
        if getattr(core, "actions", None) is actions_package:
            delattr(core, "actions")
        if getattr(services, "system", None) is system_package:
            delattr(services, "system")

BANNED_MODULES = {
    "core.plugins.adapter",
    "core.plugins.integrity",
    "core.plugins.package",
    "core.plugins.resolver",
    "core.plugins.sandbox",
    "core.plugins.scanner",
    "utils.marketplace",
    "utils.plugin_analytics",
    "utils.plugin_base",
    "utils.plugin_cdn_client",
    "utils.plugin_installer",
    "utils.plugin_marketplace",
}

PRESENTATION_ROOTS = (
    SOURCE / "ui",
    SOURCE / "cli",
)

MUTATOR_PREFIXES = (
    "apply_",
    "connect",
    "create_",
    "delete",
    "disable",
    "enable",
    "install",
    "pair",
    "power_",
    "remove",
    "restart",
    "restore",
    "set_",
    "start",
    "stop",
    "update",
)


def _python_files() -> list[Path]:
    return sorted(SOURCE.rglob("*.py"))


def _cli_operation_ids() -> set[str]:
    """Derive public CLI leaves from the canonical argparse surface."""
    from cli.parser import build_parser

    operations: set[str] = set()

    def walk(parser: argparse.ArgumentParser, prefix: tuple[str, ...] = ()) -> None:
        subparser_actions = [
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        ]
        if subparser_actions:
            for action in subparser_actions:
                for name, child in action.choices.items():
                    walk(child, (*prefix, str(name)))
            return
        positional_choice = next(
            (
                action
                for action in parser._actions
                if not action.option_strings
                and action.dest in {"action", "command"}
                and action.choices
            ),
            None,
        )
        if positional_choice is None:
            operations.add(f"cli:{' '.join(prefix)}")
            return
        for choice in positional_choice.choices:
            operations.add(f"cli:{' '.join((*prefix, str(choice)))}")

    walk(build_parser())
    return operations


def _imports(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _direct_subprocess_calls(tree: ast.AST) -> list[int]:
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        owner = node.func.value
        if isinstance(owner, ast.Name) and owner.id == "subprocess" and node.func.attr in {
            "call",
            "check_call",
            "check_output",
            "Popen",
            "run",
        }:
            lines.append(node.lineno)
    return lines


def _literal_strings(node: ast.AST) -> list[str] | None:
    if not isinstance(node, (ast.List, ast.Tuple)):
        return None
    values: list[str] = []
    for item in node.elts:
        if not isinstance(item, ast.Constant) or not isinstance(item.value, str):
            return None
        values.append(item.value)
    return values


def _literal_command(call: ast.Call) -> tuple[str, list[str]] | None:
    if not isinstance(call.func, ast.Attribute):
        return None
    if call.func.attr in {"run", "Popen", "check_call", "check_output"} and call.args:
        vector = _literal_strings(call.args[0])
        if vector:
            return vector[0], vector[1:]
    if call.func.attr == "run_command" and len(call.args) >= 2:
        command = call.args[0]
        arguments = _literal_strings(call.args[1])
        if isinstance(command, ast.Constant) and isinstance(command.value, str) and arguments is not None:
            return command.value, arguments
    return None


def _guarded_subprocess_errors(path: Path, tree: ast.AST) -> list[str]:
    """Reject direct host execution while allowing classified read-only agent probes."""
    errors: list[str] = []
    relative = path.relative_to(SOURCE)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        owner = node.func.value
        direct_subprocess = (
            isinstance(owner, ast.Name)
            and owner.id == "subprocess"
            and node.func.attr in {"call", "check_call", "check_output", "Popen", "run"}
        )
        literal = _literal_command(node)
        if literal is not None and classify_command(*literal) == "host":
            errors.append(f"direct host command at {relative}:{node.lineno}: {literal[0]}")
        if not direct_subprocess:
            continue
        if relative == Path("cli/main.py"):
            enclosing = next(
                (
                    function
                    for function in ast.walk(tree)
                    if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and function.lineno <= node.lineno <= (function.end_lineno or function.lineno)
                ),
                None,
            )
            if enclosing is not None and enclosing.name == "run_operation" and "execution_allowed" in ast.unparse(enclosing):
                continue
        if str(relative).startswith("core/agents/"):
            enclosing = next(
                (
                    function
                    for function in ast.walk(tree)
                    if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and function.lineno <= node.lineno <= (function.end_lineno or function.lineno)
                ),
                None,
            )
            guard_source = ast.unparse(enclosing) if enclosing is not None else ""
            if "classify_command" in guard_source or "execution_allowed" in guard_source:
                continue
            if literal is not None and classify_command(*literal) in {"read_only", "session", "manual_only"}:
                continue
        errors.append(f"unguarded direct subprocess at {relative}:{node.lineno}")
    return errors


def _unclassified_service_calls(path: Path, tree: ast.AST) -> list[str]:
    """Reject mutator-like service calls without an explicit non-host class."""
    errors: list[str] = []
    relative = path.relative_to(SOURCE)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if not node.func.attr.startswith(MUTATOR_PREFIXES):
            continue
        owner = node.func.value
        if not isinstance(owner, ast.Name) or not owner.id.endswith(("Manager", "Service", "Utils", "Ops", "Controller", "Auditor", "Scheduler")):
            continue
        classification = presentation_operation_class(owner.id, node.func.attr)
        if classification not in {"app_state", "session"}:
            errors.append(
                f"unclassified service mutation at {relative}:{node.lineno}: "
                f"{owner.id}.{node.func.attr}"
            )
    return errors


def _unguarded_command_runner_calls(path: Path, tree: ast.AST) -> list[str]:
    """Reject presentation runners unless the call is classified or Action Center owned."""
    errors: list[str] = []
    relative = path.relative_to(SOURCE)
    functions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "run_command" or not isinstance(node.func.value, ast.Attribute):
            continue
        owner = node.func.value
        if not (
            isinstance(owner.value, ast.Name)
            and owner.value.id == "self"
            and owner.attr.endswith("runner")
        ):
            continue
        if any(keyword.arg == "authority" for keyword in node.keywords):
            continue
        enclosing = next(
            (
                function
                for function in functions
                if function.lineno <= node.lineno <= (function.end_lineno or function.lineno)
            ),
            None,
        )
        guard_source = ast.unparse(enclosing) if enclosing is not None else ""
        if "classify_command" in guard_source or "execution_allowed" in guard_source:
            continue
        literal = _literal_command(node)
        if literal is not None and classify_command(*literal) in {"read_only", "session"}:
            continue
        errors.append(f"unguarded CommandRunner call at {relative}:{node.lineno}")
    return errors


def validate() -> list[str]:
    errors = validate_product_catalog()
    # v29 task metadata is a second, product-facing projection of the audited
    # action definitions. Keep its lifecycle and safety invariants in the
    # same contract gate as the legacy catalog instead of relying on UI tests.
    errors.extend(f"task catalog: {error}" for error in validate_task_catalog())
    errors.extend(
        f"route classification: {error}"
        for error in validate_route_classifications(route.id for route in all_routes())
    )
    action_classes = action_classifications(definition for definition in _action_definitions())
    if set(action_classes) != {str(definition.id) for definition in _action_definitions()}:
        errors.append("action classification inventory is incomplete")
    utility_ids = tuple(record.get("id") for record in TASK_ROUTE_RECORDS)
    if utility_ids[:5] != ("home", "install", "tune", "fix", "update"):
        errors.append("v29 utility shell must expose Home, Install, Tune, Fix, and Update first")
    if set(TASK_ROUTE_REDIRECTS) != {"changes", "maintenance:action-center"}:
        errors.append("v29 compatibility redirects must cover changes and maintenance:action-center")
    action_center_source = (SOURCE / "core" / "actions" / "center.py").read_text(encoding="utf-8")
    if "def execute_next" in action_center_source:
        errors.append("legacy ActionCenterService.execute_next remains an execution path")
    queue_source = (SOURCE / "core" / "actions" / "queue.py").read_text(encoding="utf-8")
    if "execution_disabled = True" not in queue_source:
        errors.append("legacy ActionQueue is not explicitly marked read-only")
    entries = product_catalog()
    definitions = _action_definitions()
    retired_route_ids = {
        "maintenance:smart-updates",
        "settings:advanced",
    }
    active_route_ids = {entry.route_id for entry in entries}
    leaked_retired = sorted(active_route_ids & retired_route_ids)
    if leaked_retired:
        errors.append(
            "retired routes remain in the live catalog: "
            + ", ".join(leaked_retired)
        )

    for definition in definitions:
        if definition.operation_class not in {"host", "app_state", "session", "manual_only"}:
            errors.append(f"action {definition.id} has no valid operation class")
        if not definition.supported_variants:
            errors.append(f"action {definition.id} has no Fedora variant policy")
        if not definition.affected_resources:
            errors.append(f"action {definition.id} has no affected-resource declaration")

    operation_ids = _cli_operation_ids()
    errors.extend(
        validate_public_operation_inventory(
            operation_ids,
            known_action_ids=(definition.id for definition in definitions),
        )
    )

    for module in BANNED_MODULES:
        path = SOURCE / Path(*module.split(".")).with_suffix(".py")
        if path.exists():
            errors.append(f"retired executable extension module remains packaged: {module}")

    for path in _python_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError) as exc:
            errors.append(f"cannot parse {path.relative_to(ROOT)}: {exc}")
            continue
        banned = sorted(_imports(tree) & BANNED_MODULES)
        for module in banned:
            errors.append(f"{path.relative_to(ROOT)} imports retired module {module}")

        if any(path == root or root in path.parents for root in PRESENTATION_ROOTS):
            errors.extend(_guarded_subprocess_errors(path, tree))
            errors.extend(_unclassified_service_calls(path, tree))
            errors.extend(_unguarded_command_runner_calls(path, tree))

    cli_source = (SOURCE / "cli" / "main.py").read_text(encoding="utf-8")
    # V27 keeps the public CLI boundary deliberately small.  The old
    # ``create_public_plans`` helper belonged to the retired specialist
    # command registry; the maintained equivalent is the typed Action Center
    # planner used by the canonical command handlers.
    if "_create_action_center_plan" not in cli_source or "closed_action_definition_required" not in cli_source:
        errors.append("CLI execution boundary is missing its closed Action Center plan gate")
    settings_source = (SOURCE / "ui" / "settings_tab.py").read_text(encoding="utf-8")
    if "self.mode_combo" in settings_source:
        errors.append("retired global navigation mode control remains visible")
    navigation_mode_source = (SOURCE / "utils" / "navigation_mode.py").read_text(encoding="utf-8")
    if "return NavigationMode.ADVANCED" not in navigation_mode_source:
        errors.append("unified Specialist Tools navigation is not enforced")

    # Verify decommissioned subsystems are absent
    if (SOURCE / "core" / "agents").exists():
        errors.append("retired core.agents package remains present")
    if (SOURCE / "daemon").exists():
        errors.append("retired daemon package remains present")
    if (SOURCE / "api").exists():
        errors.append("retired api package remains present")
    if (SOURCE / "ui" / "community_tab.py").exists():
        errors.append("retired community tab remains present")
    if (SOURCE / "utils" / "daemon.py").exists():
        errors.append("retired daemon.py remains present")
    if (SOURCE / "utils" / "api_server.py").exists():
        errors.append("retired api_server.py remains present")

    scheduler_source = (SOURCE / "utils" / "scheduler.py").read_text(encoding="utf-8")
    if "PrivilegedCommand" in scheduler_source or "notify_preset_applied" in scheduler_source:
        errors.append("scheduler still contains unattended host-mutation code")
    cloud_sync_source = (SOURCE / "services" / "storage" / "cloud_sync.py").read_text(encoding="utf-8")
    for retired_symbol in ("PRESETS_INDEX_URL", "fetch_community_presets", "download_preset"):
        if retired_symbol in cloud_sync_source:
            errors.append(f"retired public preset distribution remains active: {retired_symbol}")
    plugin_metadata_source = (SOURCE / "core" / "plugins" / "metadata.py").read_text(encoding="utf-8")
    for retired_symbol in ("ReviewAggregate", "PublisherVerification", "rating_average", "review_count"):
        if retired_symbol in plugin_metadata_source:
            errors.append(f"retired marketplace metadata remains active: {retired_symbol}")
    plugin_loader_source = (SOURCE / "core" / "plugins" / "loader.py").read_text(encoding="utf-8")
    for retired_symbol in ("HotReloadRequest", "HotReloadResult", "request_reload"):
        if retired_symbol in plugin_loader_source:
            errors.append(f"retired external hot-reload API remains active: {retired_symbol}")
    sandbox_source = (SOURCE / "services" / "security" / "sandbox.py").read_text(encoding="utf-8")
    if "PluginIsolationManager" in sandbox_source:
        errors.append("retired advisory plugin-isolation API remains active")
    if "install_firejail" in sandbox_source or "PrivilegedCommand" in sandbox_source:
        errors.append("application sandbox service still exposes a direct host installer")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"[product-contract] ERROR: {error}")
        return 1
    print(
        f"[product-contract] OK: {len(product_catalog())} routes, "
        "classified actions, built-in-only plugins, and guarded entrypoints"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
