#!/usr/bin/env python3
"""Version-neutral architecture, size, and annotation release gate."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "loofi-fedora-tweaks"

BUDGETED_EXTRACTED_MODULES = frozenset(
    {
        "cli/parser.py",
        "cli/commands/readiness_commands.py",
        "ui/main_window_interactions.py",
        "ui/main_window_services.py",
        "core/diagnostics/release_models.py",
        "ui/maintenance_updates.py",
        "ui/maintenance_action_center.py",
    }
)

# These are declarative dispatch/assembly functions. Splitting them further
# would scatter one public grammar or one screen lifecycle without reducing
# mutation authority. Their business logic already lives in domain handlers.
LONG_FUNCTION_EXCEPTIONS = {
    ("cli/parser.py", "build_parser"): "single declarative argparse grammar",
    ("cli/commands/readiness_commands.py", "_cmd_readiness_action"): "compatibility dispatcher over domain services",
    ("cli/commands/readiness_commands.py", "cmd_action_center"): "single machine-readable Action Center protocol dispatcher",
    ("ui/maintenance_action_center.py", "__init__"): "declarative construction of one lifecycle screen",
}


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _runtime_files() -> list[Path]:
    return sorted(path for path in SOURCE.rglob("*.py") if "__pycache__" not in path.parts)


def _fully_annotated(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    parameters = [
        argument
        for argument in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
        if argument.arg not in {"self", "cls"}
    ]
    if node.args.vararg is not None:
        parameters.append(node.args.vararg)
    if node.args.kwarg is not None:
        parameters.append(node.args.kwarg)
    return node.returns is not None and all(argument.annotation is not None for argument in parameters)


def _system_check_errors() -> list[str]:
    """Validate the optional canonical System Check domain when present."""
    root = SOURCE / "core" / "system_check"
    if not root.exists():
        return []
    errors: list[str] = []
    required = {"__init__.py", "mappings.py", "models.py", "service.py"}
    missing = sorted(required - {path.name for path in root.glob("*.py")})
    if missing:
        errors.append(f"System Check domain is incomplete: {', '.join(missing)}")
        return errors
    for path in sorted(root.glob("*.py")):
        tree = _tree(path)
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imports.update(
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        if any(module.startswith("PyQt6") for module in imports):
            errors.append(f"System Check imports PyQt: {path.relative_to(SOURCE)}")
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess":
                errors.append(f"System Check duplicates a direct subprocess probe: {path.relative_to(SOURCE)}:{node.lineno}")
    service_tree = _tree(root / "service.py")
    quick_sources = next(
        (
            ast.literal_eval(node.value)
            for node in service_tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "QUICK_PROFILE_SOURCES" for target in node.targets)
        ),
        (),
    )
    expected_sources = (
        "state-integrity",
        "maintenance",
        "storage-reclaim",
        "action-center",
        "pending-reboot",
    )
    if quick_sources != expected_sources:
        errors.append(f"System Check quick profile changed: expected {expected_sources}, got {quick_sources}")
    model_tree = _tree(root / "models.py")
    frozen_models = {
        node.name
        for node in model_tree.body
        if isinstance(node, ast.ClassDef)
        and any(
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Name)
            and decorator.func.id == "dataclass"
            and any(keyword.arg == "frozen" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True for keyword in decorator.keywords)
            for decorator in node.decorator_list
        )
    }
    required_models = {"FindingEvidence", "SystemFinding", "CheckSourceError", "SystemCheckResult"}
    if not required_models.issubset(frozen_models):
        errors.append(f"System Check models are not all frozen: {sorted(required_models - frozen_models)}")
    return errors


def validate() -> list[str]:
    errors = _system_check_errors()
    files = _runtime_files()
    ranked = sorted(
        ((sum(bool(line.strip()) for line in path.read_text(encoding="utf-8").splitlines()), path) for path in files),
        reverse=True,
    )
    for line_count, path in ranked[:5]:
        if line_count >= 1000:
            errors.append(f"production module exceeds 999 non-empty lines: {path.relative_to(SOURCE)} ({line_count})")

    functions: list[tuple[Path, ast.FunctionDef | ast.AsyncFunctionDef]] = []
    for path in files:
        functions.extend(
            (path, node)
            for node in ast.walk(_tree(path))
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        )
    annotated = sum(_fully_annotated(node) for _, node in functions)
    ratio = annotated / len(functions) if functions else 1.0
    if ratio < 0.85:
        errors.append(f"fully annotated runtime functions below 85%: {annotated}/{len(functions)} ({ratio:.2%})")

    cli_main = SOURCE / "cli" / "main.py"
    main_node = next(
        node
        for node in _tree(cli_main).body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "main"
    )
    main_length = (main_node.end_lineno or main_node.lineno) - main_node.lineno + 1
    if main_length > 150:
        errors.append(f"CLI main() exceeds 150 lines: {main_length}")

    for relative in BUDGETED_EXTRACTED_MODULES:
        path = SOURCE / relative
        for node in ast.walk(_tree(path)):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            length = (node.end_lineno or node.lineno) - node.lineno + 1
            if length > 100 and (relative, node.name) not in LONG_FUNCTION_EXCEPTIONS:
                errors.append(f"budgeted function exceeds 100 lines without rationale: {relative}:{node.lineno} {node.name} ({length})")

    authority_files = {
        "core/navigation/manifest.py": ("def _route(", "= NavigationRoute("),
        "core/navigation/destinations.py": ("def _placement(", "= RoutePlacement(", "= SectionDefinition(", "= Destination("),
        "core/plugins/spec.py": ("PluginSpec(",),
    }
    for relative, forbidden in authority_files.items():
        source = (SOURCE / relative).read_text(encoding="utf-8")
        for marker in forbidden:
            if marker in source:
                errors.append(f"legacy catalog view declares metadata instead of projecting it: {relative} ({marker})")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"[architecture] ERROR: {error}")
        return 1
    print("[architecture] OK: catalog authority, System Check, module/function budgets, CLI main, and 85% annotations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
