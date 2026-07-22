"""Compatibility plugin-spec view generated from the canonical v18 catalog."""

from __future__ import annotations

from core.catalog_models import PluginSpec, PluginVisibility
from core.product_catalog import catalog_plugins

BUILTIN_PLUGIN_SPECS: tuple[PluginSpec, ...] = catalog_plugins()
BUILTIN_SPEC_BY_ID = {spec.id: spec for spec in BUILTIN_PLUGIN_SPECS}

__all__ = [
    "BUILTIN_PLUGIN_SPECS",
    "BUILTIN_SPEC_BY_ID",
    "PluginSpec",
    "PluginVisibility",
]
