"""Pure data contracts for v15 navigation and visibility decisions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import FrozenSet

from core.catalog_models import (  # noqa: F401 - stable navigation re-exports
    Destination,
    FedoraVariant,
    RoutePlacement,
    SectionDefinition,
)


class NavigationMode(Enum):
    """User-facing navigation modes introduced for v15."""

    STANDARD = "standard"
    ADVANCED = "advanced"


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
class NavigationContext:
    """Inputs used by the deterministic navigation policy."""

    mode: NavigationMode = NavigationMode.STANDARD
    installed_components: FrozenSet[str] = field(
        default_factory=lambda: frozenset({"core"})
    )
    fedora_variant: FedoraVariant = FedoraVariant.UNKNOWN
    capabilities: FrozenSet[str] = field(default_factory=frozenset)
    incompatible_plugin_ids: FrozenSet[str] = field(default_factory=frozenset)
    favorite_route_ids: FrozenSet[str] = field(default_factory=frozenset)

    @classmethod
    def from_platform_profile(
        cls,
        profile: object,
        *,
        mode: NavigationMode = NavigationMode.STANDARD,
        installed_components: FrozenSet[str] = frozenset({"core"}),
        incompatible_plugin_ids: FrozenSet[str] = frozenset(),
        favorite_route_ids: FrozenSet[str] = frozenset(),
    ) -> "NavigationContext":
        """Build navigation facts from the immutable platform snapshot.

        Unknown values intentionally remain unknown and therefore cannot make a
        route appear supported.  This keeps navigation a presentation policy,
        not a second, optimistic platform detector.
        """
        from core.catalog_models import FedoraVariant
        from core.platform.profile import DeploymentBackend

        raw_backend = getattr(profile, "deployment_backend", DeploymentBackend.UNKNOWN)
        raw_backend_value = getattr(raw_backend, "value", raw_backend)
        try:
            # Accept the historical ``dnf`` spelling from injected test or
            # plugin doubles, but keep the canonical profile value dnf5.
            backend = DeploymentBackend("dnf5" if raw_backend_value == "dnf" else raw_backend_value)
        except (TypeError, ValueError):
            backend = DeploymentBackend.UNKNOWN
        is_atomic = bool(getattr(profile, "is_atomic", False))
        backend_is_atomic = backend.is_atomic
        # Contradictory injected facts are not safe to classify as either
        # traditional or atomic.  Production PlatformProfile instances are
        # internally consistent; this guard protects structural callers.
        contradictory = (backend is DeploymentBackend.DNF5 and is_atomic) or (
            backend_is_atomic and not is_atomic
        )
        if backend in {DeploymentBackend.UNKNOWN, DeploymentBackend.BOOTC} or contradictory:
            variant = FedoraVariant.UNKNOWN
        elif backend is DeploymentBackend.RPM_OSTREE and (backend_is_atomic or is_atomic):
            variant = FedoraVariant.ATOMIC
        else:
            variant = FedoraVariant.TRADITIONAL

        capabilities: set[str] = set()
        backend_value = backend.value
        if backend_value in {DeploymentBackend.DNF5.value, "dnf"}:
            capabilities.add("dnf5")
        elif backend_value == DeploymentBackend.RPM_OSTREE.value:
            capabilities.add("rpm-ostree")
        elif backend_value == DeploymentBackend.BOOTC.value:
            capabilities.add("bootc")
        desktop = str(getattr(getattr(profile, "desktop", None), "value", getattr(profile, "desktop", "unknown")))
        session = str(getattr(getattr(profile, "session_type", None), "value", getattr(profile, "session_type", "unknown")))
        if desktop != "unknown":
            capabilities.add(f"desktop:{desktop}")
        if session != "unknown":
            capabilities.add(f"session:{session}")
        if getattr(profile, "is_fedora", False) and backend is not DeploymentBackend.UNKNOWN:
            capabilities.add("fedora")

        return cls(
            mode=mode,
            installed_components=installed_components,
            fedora_variant=variant,
            capabilities=frozenset(capabilities),
            incompatible_plugin_ids=incompatible_plugin_ids,
            favorite_route_ids=favorite_route_ids,
        )


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
