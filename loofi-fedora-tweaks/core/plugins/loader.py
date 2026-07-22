"""Built-in-only, route-time plugin loader for Haven."""

from __future__ import annotations

import importlib
import logging
import sys

from core.plugins.compat import CompatibilityDetector
from core.plugins.interface import PluginInterface
from core.plugins.registry import PluginRegistry
from core.plugins.spec import BUILTIN_PLUGIN_SPECS, BUILTIN_SPEC_BY_ID
from version import __version__ as APP_VERSION

log = logging.getLogger(__name__)


class PluginLoader:
    """Register data-only built-in specs and construct one widget on demand."""

    def __init__(
        self,
        registry: PluginRegistry | None = None,
        detector: CompatibilityDetector | None = None,
    ) -> None:
        self._registry = registry if registry is not None else PluginRegistry.instance()
        self._detector = detector if detector is not None else CompatibilityDetector()
        self._builtin_widgets: dict[str, object] = {}

    @staticmethod
    def _parse_version(ver_str: str) -> tuple[int, ...]:
        if not ver_str or not isinstance(ver_str, str):
            return (0,)
        try:
            parts = ver_str.strip().lstrip("v").split(".")
            return tuple(int(part) for part in parts if part.isdigit())
        except (ValueError, AttributeError):
            return (0,)

    def _check_version_compatibility(
        self,
        plugin_id: str,
        min_version: str,
        max_version: str,
    ) -> tuple[bool, str]:
        """Compatibility helper retained for built-in diagnostics/tests."""
        app_version = self._parse_version(APP_VERSION)
        if min_version and app_version < self._parse_version(min_version):
            return False, f"Plugin requires app version >= {min_version}, current: {APP_VERSION}"
        if max_version and app_version > self._parse_version(max_version):
            return False, f"Plugin supports app version <= {max_version}, current: {APP_VERSION}"
        return True, ""

    def load_builtins(self, context: dict | None = None) -> list[str]:
        """Compatibility bulk loader; startup must use register_builtin_specs."""
        loaded: list[str] = []
        for spec in BUILTIN_PLUGIN_SPECS:
            try:
                plugin = self.load_builtin(spec.id, context=context)
                loaded.append(plugin.metadata().id)
            except (ImportError, AttributeError, TypeError, ValueError) as exc:
                log.warning("Failed to load built-in plugin %s: %s", spec.id, exc)
        return loaded

    def register_builtin_specs(self) -> list[str]:
        registered: list[str] = []
        for spec in BUILTIN_PLUGIN_SPECS:
            existing = self._registry.get_spec(spec.id)
            if existing is None:
                self._registry.register_spec(spec)
                registered.append(spec.id)
            elif existing != spec:
                raise ValueError(f"Conflicting plugin spec id: {spec.id!r}")
        return registered

    def load_builtin(self, plugin_id: str, context: dict | None = None) -> PluginInterface:
        cached = self._registry.get(plugin_id)
        if cached is not None:
            if context:
                cached.set_context(context)
            return cached

        spec = self._registry.get_spec(plugin_id) or BUILTIN_SPEC_BY_ID.get(plugin_id)
        if spec is None:
            raise KeyError(f"Unknown built-in plugin: {plugin_id!r}")
        if self._registry.get_spec(plugin_id) is None:
            self._registry.register_spec(spec)
        plugin = self._import_plugin(spec.module, spec.class_name)
        if context:
            plugin.set_context(context)
        self._registry.cache_builtin(spec, plugin)
        return plugin

    def load_builtin_widget(self, plugin_id: str, context: dict | None = None):
        if plugin_id not in self._builtin_widgets:
            self._builtin_widgets[plugin_id] = self.load_builtin(
                plugin_id,
                context=context,
            ).create_widget()
        return self._builtin_widgets[plugin_id]

    @staticmethod
    def _import_plugin(module_path: str, class_name: str) -> PluginInterface:
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        if not (isinstance(cls, type) and issubclass(cls, PluginInterface)):
            sys.modules.pop(module_path, None)
            importlib.invalidate_caches()
            mod = importlib.import_module(module_path)
            cls = getattr(mod, class_name)
        if not (isinstance(cls, type) and issubclass(cls, PluginInterface)):
            raise TypeError(f"{class_name} does not subclass PluginInterface")
        return cls()

    def load_external(
        self,
        context: dict | None = None,
        directory: str | None = None,
    ) -> list[str]:
        """Never scan or import external code; retain a stable empty response."""
        del context, directory
        log.warning("External executable plugins were retired in Haven and were not loaded.")
        return []
