"""Pure data contracts for v15 navigation and visibility decisions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import FrozenSet


class NavigationMode(Enum):
    """User-facing navigation modes introduced for v15."""

    STANDARD = "standard"
    ADVANCED = "advanced"


class FedoraVariant(Enum):
    """Fedora installation variants relevant to navigation capability policy."""

    TRADITIONAL = "traditional"
    ATOMIC = "atomic"
    UNKNOWN = "unknown"


class NavigationDecision(Enum):
    """Visibility outcome for a route in the current navigation context."""

    VISIBLE = "visible"
    HIDDEN = "hidden"
    GATED = "gated"
    UNAVAILABLE = "unavailable"


class DirectLinkBehavior(Enum):
    """How a direct route request should be handled by the shell."""

    ALLOW = "allow"
    REDIRECT = "redirect"
    EXPLAIN = "explain"


@dataclass(frozen=True)
class Destination:
    """A shell destination that groups existing canonical route IDs."""

    id: str
    label: str
    icon: str
    default_route_id: str
    route_ids: tuple[str, ...]
    advanced_only: bool = False


@dataclass(frozen=True)
class RoutePlacement:
    """Destination, section, and compatibility metadata for one route."""

    route_id: str
    destination_id: str
    section_id: str
    advanced_only: bool = False
    component_id: str = "core"
    required_capabilities: FrozenSet[str] = field(default_factory=frozenset)
    allowed_variants: FrozenSet[FedoraVariant] = field(
        default_factory=lambda: frozenset(
            {FedoraVariant.TRADITIONAL, FedoraVariant.ATOMIC}
        )
    )
    redirect_route_id: str | None = None
    discoverable: bool = True


@dataclass(frozen=True)
class NavigationContext:
    """Inputs used by the deterministic navigation policy."""

    mode: NavigationMode = NavigationMode.STANDARD
    installed_components: FrozenSet[str] = field(
        default_factory=lambda: frozenset({"core", "specialist"})
    )
    fedora_variant: FedoraVariant = FedoraVariant.TRADITIONAL
    capabilities: FrozenSet[str] = field(default_factory=lambda: frozenset({"dnf"}))
    incompatible_plugin_ids: FrozenSet[str] = field(default_factory=frozenset)
    favorite_route_ids: FrozenSet[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class NavigationPolicyResult:
    """Complete policy outcome for one requested route."""

    requested_route_id: str
    route_id: str | None
    destination_id: str
    section_id: str
    decision: NavigationDecision
    reason: str
    required_mode: NavigationMode | None
    required_component: str | None
    required_package: str | None
    required_capabilities: FrozenSet[str]
    fallback_route_id: str
    search_visible: bool
    direct_link_behavior: DirectLinkBehavior
    redirect_route_id: str | None
    is_favorite: bool
    risk: str
