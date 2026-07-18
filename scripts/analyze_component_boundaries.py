#!/usr/bin/env python3
"""Build deterministic Phase 9 import and RPM ownership evidence."""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import sys
from collections import deque
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SOURCE_ROOT = ROOT / "loofi-fedora-tweaks"
SPEC_PATH = ROOT / "loofi-fedora-tweaks.spec"

if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from core.plugins.spec import BUILTIN_PLUGIN_SPECS  # noqa: E402


def _module_name(path: Path, source_root: Path) -> str:
    relative = path.relative_to(source_root).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def discover_modules(source_root: Path) -> dict[str, Path]:
    """Map every project Python module to its source file."""
    return {
        _module_name(path, source_root): path
        for path in sorted(source_root.rglob("*.py"))
        if "__pycache__" not in path.parts
    }


def _existing_import_targets(
    node: ast.Import | ast.ImportFrom,
    *,
    current_module: str,
    current_path: Path,
    modules: dict[str, Path],
) -> set[str]:
    candidates: set[str] = set()
    if isinstance(node, ast.Import):
        candidates.update(alias.name for alias in node.names)
    else:
        if node.level:
            package = (
                current_module
                if current_path.name == "__init__.py"
                else current_module.rpartition(".")[0]
            )
            relative = "." * node.level + (node.module or "")
            try:
                base = importlib.util.resolve_name(relative, package)
            except (ImportError, ValueError):
                return set()
        else:
            base = node.module or ""
        if base:
            candidates.add(base)
            candidates.update(f"{base}.{alias.name}" for alias in node.names)

    return {
        candidate
        for candidate in candidates
        if candidate in modules and candidate != current_module
    }


def build_import_graph(modules: dict[str, Path]) -> dict[str, set[str]]:
    """Return internal import edges for every discovered project module."""
    graph = {module: set() for module in modules}
    for module, path in modules.items():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                graph[module].update(
                    _existing_import_targets(
                        node,
                        current_module=module,
                        current_path=path,
                        modules=modules,
                    )
                )
    return graph


def reachable_modules(graph: dict[str, set[str]], roots: set[str]) -> set[str]:
    """Return the internal transitive closure from existing roots."""
    visited: set[str] = set()
    queue = deque(root for root in sorted(roots) if root in graph)
    while queue:
        module = queue.popleft()
        if module in visited:
            continue
        visited.add(module)
        queue.extend(sorted(graph[module] - visited))
    return visited


def _rpm_evidence(spec_path: Path) -> dict[str, bool]:
    text = spec_path.read_text(encoding="utf-8")
    return {
        "base_owns_complete_application_tree": "%{_prefix}/lib/%{name}" in text,
        "extras_subpackage_defined": "%package extras" in text,
        "api_requires_exact_base": "Requires:       %{name} = %{epoch}:%{version}-%{release}" in text.split("%package api", 1)[-1].split("%package daemon", 1)[0],
        "daemon_requires_exact_base": "Requires:       %{name} = %{epoch}:%{version}-%{release}" in text.split("%package daemon", 1)[-1].split("%prep", 1)[0],
    }


def analyze(source_root: Path = SOURCE_ROOT, spec_path: Path = SPEC_PATH) -> dict[str, Any]:
    """Return import reachability and current RPM ownership evidence."""
    modules = discover_modules(source_root)
    graph = build_import_graph(modules)
    component_roots: dict[str, set[str]] = {}
    component_plugins: dict[str, list[str]] = {}
    for spec in BUILTIN_PLUGIN_SPECS:
        component_roots.setdefault(spec.component, set()).add(spec.module)
        component_plugins.setdefault(spec.component, []).append(spec.id)

    core_reachable = reachable_modules(graph, component_roots.get("core", set()))
    specialist_reachable = reachable_modules(
        graph, component_roots.get("specialist", set())
    )
    specialist_entries = component_roots.get("specialist", set())
    specialist_exclusive = specialist_reachable - core_reachable
    core_to_specialist_entries = sorted(
        f"{source} -> {target}"
        for source in core_reachable
        for target in graph.get(source, set())
        if target in specialist_entries
    )
    missing_entries = sorted(
        root
        for roots in component_roots.values()
        for root in roots
        if root not in modules
    )

    surface_roots = {
        "cli": {"cli.main"},
        "api": {"utils.api_server"},
        "daemon": {"daemon.runtime"},
    }
    surface_reachability = {}
    for surface, roots in surface_roots.items():
        reachable = reachable_modules(graph, roots)
        specialist_overlap = sorted(reachable & specialist_exclusive)
        surface_reachability[surface] = {
            "reachable_count": len(reachable),
            "specialist_exclusive_count": len(specialist_overlap),
            "specialist_exclusive_modules": specialist_overlap,
        }

    return {
        "schema_version": 1,
        "components": {
            component: {
                "plugin_ids": sorted(component_plugins[component]),
                "entry_modules": sorted(roots),
                "entry_module_count": len(roots),
            }
            for component, roots in sorted(component_roots.items())
        },
        "graph": {
            "project_module_count": len(modules),
            "internal_edge_count": sum(len(targets) for targets in graph.values()),
            "missing_entry_modules": missing_entries,
            "core_reachable_count": len(core_reachable),
            "specialist_reachable_count": len(specialist_reachable),
            "shared_reachable_count": len(core_reachable & specialist_reachable),
            "specialist_exclusive_count": len(specialist_exclusive),
            "core_to_specialist_entry_edges": core_to_specialist_entries,
        },
        "surface_reachability": surface_reachability,
        "rpm": _rpm_evidence(spec_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = analyze()
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
