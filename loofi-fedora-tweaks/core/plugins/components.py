"""Runtime discovery for logically isolated built-in components."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable
from pathlib import Path

from core.plugins.spec import BUILTIN_PLUGIN_SPECS, PluginSpec


def module_source_path(module: str, *, source_root: Path | None = None) -> Path:
    """Return the source path for a built-in module without importing it."""
    root = source_root or Path(__file__).resolve().parents[2]
    return root.joinpath(*module.split(".")).with_suffix(".py")


def discover_builtin_components(
    specs: Iterable[PluginSpec] = BUILTIN_PLUGIN_SPECS,
    *,
    source_root: Path | None = None,
    module_available: Callable[[str], bool] | None = None,
) -> frozenset[str]:
    """Return components whose complete built-in module set is installed.

    Built-in specifications are data-only and remain available even when a
    physical component is absent. Availability is therefore derived from the
    installed module files before navigation policy exposes component routes.
    """
    grouped: dict[str, list[PluginSpec]] = defaultdict(list)
    for spec in specs:
        grouped[spec.component].append(spec)

    probe = module_available or (
        lambda module: module_source_path(module, source_root=source_root).is_file()
    )
    return frozenset(
        component
        for component, component_specs in grouped.items()
        if component_specs and all(probe(spec.module) for spec in component_specs)
    )
