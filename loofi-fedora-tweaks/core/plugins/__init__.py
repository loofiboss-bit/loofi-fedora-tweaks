"""
core.plugins — Plugin architecture for Loofi Fedora Tweaks.

Public API:
    PluginInterface  — ABC for all plugins
    PluginMetadata   — frozen dataclass for plugin metadata
    CompatStatus     — dataclass for compatibility check results
    PluginRegistry   — singleton registry
    PluginLoader     — built-in plugin loader
    CompatibilityDetector — system compatibility checker
    External executable plugin APIs are retired.
"""

from core.plugins.compat import CompatibilityDetector
from core.plugins.interface import PluginInterface
from core.plugins.loader import PluginLoader
from core.plugins.metadata import CompatStatus, PluginMetadata
from core.plugins.registry import PluginRegistry
from core.plugins.spec import BUILTIN_PLUGIN_SPECS, PluginSpec

__all__ = [
    "PluginInterface",
    "PluginMetadata",
    "CompatStatus",
    "PluginRegistry",
    "PluginLoader",
    "CompatibilityDetector",
    "PluginSpec",
    "BUILTIN_PLUGIN_SPECS",
]
