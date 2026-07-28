"""Data-only contracts shared by the canonical v18 product catalog views."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, FrozenSet, Literal, Mapping

if TYPE_CHECKING:
    from core.plugins.metadata import PluginMetadata

RiskLevel = Literal["none", "low", "medium", "high"]
RouteVisibility = Literal["beginner", "advanced", "all"]
PluginVisibility = Literal["standard", "advanced"]


class FedoraVariant(Enum):
    """Fedora installation variants relevant to capability policy."""

    TRADITIONAL = "traditional"
    ATOMIC = "atomic"
    UNKNOWN = "unknown"


class CapabilityState(str, Enum):
    """Inert presentation state; it never grants execution authority."""

    SUPPORTED = "supported"
    READ_ONLY = "read_only"
    UNAVAILABLE = "unavailable"
    MANUAL_ONLY = "manual_only"
    NATIVE_HANDOFF = "native_handoff"
    PENDING_REBOOT = "pending_reboot"


class NativeHandoffId(str, Enum):
    """Opaque identifiers for the fixed native desktop handoff allowlist."""

    PLASMA_DISCOVER = "plasma.discover"
    PLASMA_NETWORK_CONNECTIONS = "plasma.network.connections"
    PLASMA_APPEARANCE = "plasma.appearance"
    PLASMA_DISPLAY = "plasma.display"
    PLASMA_WINDOW_MANAGEMENT = "plasma.window.management"


@dataclass(frozen=True)
class NavigationRoute:
    """A stable route users and persisted UI state can reference."""

    id: str
    label: str
    plugin_id: str
    category: str
    icon: str
    description: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    keywords: tuple[str, ...] = field(default_factory=tuple)
    risk: RiskLevel = "none"
    visibility: RouteVisibility = "all"
    subroute: str = ""


@dataclass(frozen=True)
class PluginSpec:
    """Static metadata needed to render navigation before importing plugin UI."""

    id: str
    name: str
    description: str
    icon: str
    destination_id: str
    module: str
    class_name: str
    component: str = "core"
    visibility: PluginVisibility = "standard"
    compat: Mapping[str, Any] = field(default_factory=dict)
    category: str = "System"
    badge: str = ""
    order: int = 100

    def __post_init__(self) -> None:
        required = {
            "id": self.id,
            "name": self.name,
            "destination_id": self.destination_id,
            "module": self.module,
            "class_name": self.class_name,
            "component": self.component,
        }
        missing = [name for name, value in required.items() if not str(value).strip()]
        if missing:
            raise ValueError("PluginSpec fields must not be empty: %s" % ", ".join(missing))
        if self.visibility not in {"standard", "advanced"}:
            raise ValueError("Invalid plugin visibility: %s" % self.visibility)
        object.__setattr__(self, "compat", MappingProxyType(dict(self.compat)))

    def metadata(self) -> PluginMetadata:
        """Return legacy metadata without importing the implementation module."""
        from core.plugins.metadata import PluginMetadata

        return PluginMetadata(
            id=self.id,
            name=self.name,
            description=self.description,
            category=self.category,
            icon=self.icon,
            badge=self.badge,
            compat=dict(self.compat),
            order=self.order,
        )


@dataclass(frozen=True)
class Destination:
    """A shell destination that groups canonical route IDs."""

    id: str
    label: str
    icon: str
    default_route_id: str
    route_ids: tuple[str, ...]
    advanced_only: bool = False


@dataclass(frozen=True)
class SectionDefinition:
    """Data-only presentation metadata for one destination section."""

    id: str
    destination_id: str
    label: str
    icon: str
    order: int
    default_route_id: str
    description: str = ""


@dataclass(frozen=True)
class RoutePlacement:
    """Destination, section, capability, and compatibility metadata for a route."""

    route_id: str
    destination_id: str
    section_id: str
    advanced_only: bool = False
    component_id: str = "core"
    required_capabilities: FrozenSet[str] = field(default_factory=frozenset)
    allowed_variants: FrozenSet[FedoraVariant] = field(
        default_factory=lambda: frozenset({FedoraVariant.TRADITIONAL, FedoraVariant.ATOMIC})
    )
    redirect_route_id: str | None = None
    discoverable: bool = True
    native_handoff_id: NativeHandoffId | None = None
