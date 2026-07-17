from __future__ import annotations

from typing import Iterator

from core.plugins.interface import PluginInterface
from core.plugins.spec import PluginSpec

# Explicit category ordering — controls sidebar top-to-bottom sequence.
# Lower value = higher in sidebar.  Categories not listed sort after all listed ones.
CATEGORY_ORDER: dict[str, int] = {
    "System": 0,
    "Packages": 1,
    "Hardware": 2,
    "Network": 3,
    "Security": 4,
    "Appearance": 5,
    "Tools": 6,
    "Maintenance": 7,
}

# Category icons — semantic ids resolved by ui/icon_pack.py.
CATEGORY_ICONS: dict[str, str] = {
    "Home": "home",
    "Software & Updates": "packages-software",
    "System & Hardware": "hardware-performance",
    "Network & Security": "security-shield",
    "Desktop & Settings": "appearance-theme",
    "More": "developer-tools",
    "System": "overview-dashboard",
    "Packages": "packages-software",
    "Hardware": "hardware-performance",
    "Network": "network-connectivity",
    "Security": "security-shield",
    "Appearance": "appearance-theme",
    "Tools": "developer-tools",
    "Maintenance": "maintenance-health",
}


class PluginRegistry:
    """
    Singleton registry holding all registered plugin instances.

    Tabs self-register via PluginLoader. MainWindow sources its
    sidebar entirely from this registry.
    """

    _instance: "PluginRegistry | None" = None

    def __init__(self) -> None:
        self._specs: dict[str, PluginSpec] = {}
        self._spec_order: list[str] = []
        self._plugins: dict[str, PluginInterface] = {}  # id -> plugin
        self._order: list[str] = []                      # insertion/sort order

    @classmethod
    def instance(cls) -> "PluginRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton — for use in tests only."""
        cls._instance = None

    def register(self, plugin: PluginInterface) -> None:
        """
        Register a plugin. Raises ValueError if id is already registered.
        Preserves order by PluginMetadata.order, then insertion order.
        """
        meta = plugin.metadata()
        if meta.id in self._specs:
            raise ValueError(f"Plugin id is reserved by a built-in spec: {meta.id!r}")
        if meta.id in self._plugins:
            raise ValueError(f"Plugin id already registered: {meta.id!r}")
        self._plugins[meta.id] = plugin
        self._order.append(meta.id)
        self._sort_order()

    def cache_builtin(self, spec: PluginSpec, plugin: PluginInterface) -> None:
        """Cache a validated runtime instance for its reserved built-in spec."""
        if self._specs.get(spec.id) != spec:
            raise ValueError(f"Built-in plugin spec is not registered: {spec.id!r}")
        metadata = plugin.metadata()
        if metadata.id != spec.id:
            raise ValueError(
                "Plugin spec id %r does not match runtime id %r"
                % (spec.id, metadata.id)
            )
        if spec.id in self._plugins:
            raise ValueError(f"Plugin id already registered: {spec.id!r}")
        self._plugins[spec.id] = plugin
        self._order.append(spec.id)
        self._sort_order()

    def register_spec(self, spec: PluginSpec) -> None:
        """Register static plugin data without importing or constructing UI."""
        if spec.id in self._specs:
            raise ValueError(f"Plugin spec id already registered: {spec.id!r}")
        self._specs[spec.id] = spec
        self._spec_order.append(spec.id)
        self._sort_spec_order()

    def get_spec(self, plugin_id: str) -> PluginSpec | None:
        return self._specs.get(plugin_id)

    def list_specs(self) -> list[PluginSpec]:
        """Return all static specifications in stable navigation order."""
        return [self._specs[pid] for pid in self._spec_order if pid in self._specs]

    def unregister_spec(self, plugin_id: str) -> None:
        """Remove a static specification without touching a cached instance."""
        self._specs.pop(plugin_id, None)
        if plugin_id in self._spec_order:
            self._spec_order.remove(plugin_id)

    def unregister(self, plugin_id: str) -> None:
        """Remove a plugin by id. Silent no-op if not found."""
        self._plugins.pop(plugin_id, None)
        if plugin_id in self._order:
            self._order.remove(plugin_id)

    def get(self, plugin_id: str) -> PluginInterface | None:
        return self._plugins.get(plugin_id)

    def list_all(self) -> list[PluginInterface]:
        """Return all plugins in sorted order."""
        return [self._plugins[pid] for pid in self._order if pid in self._plugins]

    def list_by_category(self, category: str) -> list[PluginInterface]:
        return [p for p in self.list_all() if p.metadata().category == category]

    def categories(self) -> list[str]:
        """Return unique categories in order of first appearance."""
        seen: list[str] = []
        for pid in self._order:
            if pid in self._plugins:
                cat = self._plugins[pid].metadata().category
                if cat not in seen:
                    seen.append(cat)
        return seen

    def _sort_order(self) -> None:
        """Re-sort _order list by (CATEGORY_ORDER rank, plugin.order, insertion)."""
        _fallback = max(CATEGORY_ORDER.values()) + 1 if CATEGORY_ORDER else 0
        self._order.sort(key=lambda pid: (
            CATEGORY_ORDER.get(self._plugins[pid].metadata().category, _fallback),
            self._plugins[pid].metadata().order,
        ))

    def _sort_spec_order(self) -> None:
        """Sort specifications without consulting runtime plugin instances."""
        fallback = max(CATEGORY_ORDER.values()) + 1 if CATEGORY_ORDER else 0
        self._spec_order.sort(key=lambda pid: (
            CATEGORY_ORDER.get(self._specs[pid].category, fallback),
            self._specs[pid].order,
        ))

    def __iter__(self) -> Iterator[PluginInterface]:
        return iter(self.list_all())

    def __len__(self) -> int:
        return len(self._plugins)
