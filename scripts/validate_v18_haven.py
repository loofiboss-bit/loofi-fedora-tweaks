#!/usr/bin/env python3
"""Release gate for Haven trust-boundary and catalog contracts."""

from __future__ import annotations

import ast
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
        from core.actions.assurance import assurance_definitions
        from core.actions.catalog import ActionCatalog, _first_party_definitions
        from core.actions.metadata import with_haven_metadata

        definitions = [
            with_haven_metadata(definition)
            for definition in [*_first_party_definitions(), *assurance_definitions()]
        ]
        return list(ActionCatalog(definitions).list())
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
    SOURCE / "daemon",
    SOURCE / "core" / "agents",
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
    entries = product_catalog()
    if len({entry.route_id for entry in entries}) != 80:
        errors.append(f"stable route count changed: expected 80, got {len(entries)}")

    for definition in _action_definitions():
        if definition.operation_class not in {"host", "app_state", "session", "manual_only"}:
            errors.append(f"action {definition.id} has no valid operation class")
        if not definition.supported_variants:
            errors.append(f"action {definition.id} has no Fedora variant policy")
        if not definition.affected_resources:
            errors.append(f"action {definition.id} has no affected-resource declaration")

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
    if "execution_allowed(" not in cli_source or "action_center_required" not in cli_source:
        errors.append("CLI execution boundary is missing its fail-closed Action Center gate")
    agent_source = (SOURCE / "core" / "agents" / "agent_runner.py").read_text(encoding="utf-8")
    if "classify_command(" not in agent_source or "Action Center" not in agent_source:
        errors.append("agent raw-command boundary is missing its classification gate")
    daemon_source = (SOURCE / "utils" / "daemon.py").read_text(encoding="utf-8")
    if "install plugin" in daemon_source.lower() or "download plugin" in daemon_source.lower():
        errors.append("daemon still advertises executable extension updates")
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
    community_source = (SOURCE / "ui" / "community_tab.py").read_text(encoding="utf-8")
    for retired_symbol in (
        "refresh_marketplace",
        "download_marketplace_preset",
        "_search_marketplace_plugins",
        "_install_marketplace_plugin",
    ):
        if retired_symbol in community_source:
            errors.append(f"retired Marketplace UI API remains active: {retired_symbol}")
    sandbox_source = (SOURCE / "services" / "security" / "sandbox.py").read_text(encoding="utf-8")
    if "PluginIsolationManager" in sandbox_source:
        errors.append("retired advisory plugin-isolation API remains active")
    if "install_firejail" in sandbox_source or "PrivilegedCommand" in sandbox_source:
        errors.append("application sandbox service still exposes a direct host installer")
    handler_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (SOURCE / "daemon" / "handlers").glob("*_handler.py")
    )
    for forbidden in (
        ".install_local(",
        ".remove_local(",
        ".update_local(",
        ".start_unit(",
        ".stop_unit(",
        ".restart_unit(",
        ".open_port_local(",
        ".close_port_local(",
        ".apply_dns_local(",
    ):
        if forbidden in handler_sources:
            errors.append(f"daemon handler bypasses plan-only boundary: {forbidden}")

    for route_path in sorted((SOURCE / "api" / "routes").glob("*.py")):
        route_source = route_path.read_text(encoding="utf-8")
        if "@router.post(" in route_source or "@router.put(" in route_source or "@router.delete(" in route_source:
            errors.append(f"Web API mutation route remains: {route_path.relative_to(ROOT)}")
        route_tree = ast.parse(route_source, filename=str(route_path))
        for node in route_tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            is_get = any(
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr == "get"
                for decorator in node.decorator_list
            )
            if is_get and "AuthManager.verify_bearer_token" not in ast.unparse(node.args):
                errors.append(
                    f"Web API GET lacks bearer authentication: {route_path.relative_to(ROOT)}:{node.lineno}"
                )
    api_server_source = (SOURCE / "utils" / "api_server.py").read_text(encoding="utf-8")
    if '@app.post("/api/token")' not in api_server_source:
        errors.append("Web API token issuance route is missing")
    if "@app.get(" in api_server_source or ".mount(" in api_server_source:
        errors.append("Web API exposes an unauthenticated app-level GET or static mount")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"[haven] ERROR: {error}")
        return 1
    print("[haven] OK: 80 routes, classified actions, built-in-only plugins, and guarded entrypoints")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
