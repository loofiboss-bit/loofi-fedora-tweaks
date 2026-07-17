"""Deterministic v15 navigation policy.

The policy consumes already collected platform and compatibility facts.  It
does not import UI code, probe the host, or perform any navigation or action.
"""

from __future__ import annotations

from dataclasses import replace

from .destinations import get_destination, placement_for_route, validate_destinations
from .manifest import NavigationRoute, all_routes, resolve
from .models import (
    DirectLinkBehavior,
    FedoraVariant,
    NavigationContext,
    NavigationDecision,
    NavigationMode,
    NavigationPolicyResult,
    RoutePlacement,
)

_HOME_ROUTE_ID = "atlas_dashboard"


def _result(
    *,
    requested: str,
    route: NavigationRoute,
    placement: RoutePlacement,
    decision: NavigationDecision,
    reason: str,
    required_mode: NavigationMode | None,
    fallback_route_id: str,
    search_visible: bool,
    direct_link_behavior: DirectLinkBehavior,
    is_favorite: bool,
) -> NavigationPolicyResult:
    return NavigationPolicyResult(
        requested_route_id=requested,
        route_id=route.id,
        destination_id=placement.destination_id,
        section_id=placement.section_id,
        decision=decision,
        reason=reason,
        required_mode=required_mode,
        required_component=placement.component_id,
        required_package=None,
        required_capabilities=placement.required_capabilities,
        fallback_route_id=fallback_route_id,
        search_visible=search_visible,
        direct_link_behavior=direct_link_behavior,
        redirect_route_id=placement.redirect_route_id,
        is_favorite=is_favorite,
        risk=route.risk,
    )


class NavigationPolicy:
    """Evaluate route visibility without side effects."""

    @staticmethod
    def evaluate(
        requested_route: str,
        context: NavigationContext | None = None,
    ) -> NavigationPolicyResult:
        """Return a complete outcome for a route ID or compatibility alias."""
        context = context or NavigationContext()
        requested = str(requested_route or "").strip()
        route = resolve(requested)

        if route is None:
            return NavigationPolicyResult(
                requested_route_id=requested,
                route_id=None,
                destination_id="home",
                section_id="overview",
                decision=NavigationDecision.UNAVAILABLE,
                reason="This route is not registered.",
                required_mode=None,
                required_component=None,
                required_package=None,
                required_capabilities=frozenset(),
                fallback_route_id=_HOME_ROUTE_ID,
                search_visible=False,
                direct_link_behavior=DirectLinkBehavior.EXPLAIN,
                redirect_route_id=None,
                is_favorite=False,
                risk="none",
            )

        placement = placement_for_route(route.id)
        if placement is None:
            return NavigationPolicyResult(
                requested_route_id=requested,
                route_id=route.id,
                destination_id="home",
                section_id="overview",
                decision=NavigationDecision.UNAVAILABLE,
                reason="This route has no destination placement.",
                required_mode=None,
                required_component=None,
                required_package=None,
                required_capabilities=frozenset(),
                fallback_route_id=_HOME_ROUTE_ID,
                search_visible=False,
                direct_link_behavior=DirectLinkBehavior.EXPLAIN,
                redirect_route_id=None,
                is_favorite=route.id in context.favorite_route_ids,
                risk=route.risk,
            )

        destination = get_destination(placement.destination_id)
        fallback_route_id = (
            _HOME_ROUTE_ID
            if destination is None or destination.advanced_only
            else destination.default_route_id
        )
        is_favorite = route.id in context.favorite_route_ids
        if placement.redirect_route_id:
            redirect_result = NavigationPolicy.evaluate(
                placement.redirect_route_id,
                context,
            )
            if redirect_result.decision is not NavigationDecision.VISIBLE:
                return replace(
                    redirect_result,
                    requested_route_id=requested,
                    route_id=route.id,
                    reason=(
                        "The compatibility target is unavailable. "
                        + redirect_result.reason
                    ),
                    search_visible=False,
                    direct_link_behavior=DirectLinkBehavior.EXPLAIN,
                    redirect_route_id=None,
                    is_favorite=is_favorite,
                    risk=route.risk,
                )
            return _result(
                requested=requested,
                route=route,
                placement=placement,
                decision=NavigationDecision.HIDDEN,
                reason="This compatibility route redirects to its maintained destination.",
                required_mode=None,
                fallback_route_id=fallback_route_id,
                search_visible=False,
                direct_link_behavior=DirectLinkBehavior.REDIRECT,
                is_favorite=is_favorite,
            )

        if placement.component_id not in context.installed_components:
            return _result(
                requested=requested,
                route=route,
                placement=placement,
                decision=NavigationDecision.UNAVAILABLE,
                reason=f"The required {placement.component_id} component is not installed.",
                required_mode=(
                    NavigationMode.ADVANCED if placement.advanced_only else None
                ),
                fallback_route_id=fallback_route_id,
                search_visible=False,
                direct_link_behavior=DirectLinkBehavior.EXPLAIN,
                is_favorite=is_favorite,
            )

        if route.plugin_id in context.incompatible_plugin_ids:
            return _result(
                requested=requested,
                route=route,
                placement=placement,
                decision=NavigationDecision.UNAVAILABLE,
                reason="This route's plugin is incompatible with the current application.",
                required_mode=(
                    NavigationMode.ADVANCED if placement.advanced_only else None
                ),
                fallback_route_id=fallback_route_id,
                search_visible=False,
                direct_link_behavior=DirectLinkBehavior.EXPLAIN,
                is_favorite=is_favorite,
            )

        if context.fedora_variant not in placement.allowed_variants:
            return _result(
                requested=requested,
                route=route,
                placement=placement,
                decision=NavigationDecision.HIDDEN,
                reason="This route is not available for the current Fedora variant.",
                required_mode=(
                    NavigationMode.ADVANCED if placement.advanced_only else None
                ),
                fallback_route_id=fallback_route_id,
                search_visible=False,
                direct_link_behavior=DirectLinkBehavior.EXPLAIN,
                is_favorite=is_favorite,
            )

        missing_capabilities = placement.required_capabilities - context.capabilities
        if missing_capabilities:
            return _result(
                requested=requested,
                route=route,
                placement=placement,
                decision=NavigationDecision.UNAVAILABLE,
                reason=(
                    "Required capabilities are unavailable: "
                    + ", ".join(sorted(missing_capabilities))
                    + "."
                ),
                required_mode=(
                    NavigationMode.ADVANCED if placement.advanced_only else None
                ),
                fallback_route_id=fallback_route_id,
                search_visible=False,
                direct_link_behavior=DirectLinkBehavior.EXPLAIN,
                is_favorite=is_favorite,
            )

        if placement.advanced_only and context.mode is NavigationMode.STANDARD:
            return _result(
                requested=requested,
                route=route,
                placement=placement,
                decision=NavigationDecision.GATED,
                reason="Switch to Advanced mode to use this route.",
                required_mode=NavigationMode.ADVANCED,
                fallback_route_id=fallback_route_id,
                search_visible=False,
                direct_link_behavior=DirectLinkBehavior.EXPLAIN,
                is_favorite=is_favorite,
            )

        return _result(
            requested=requested,
            route=route,
            placement=placement,
            decision=(
                NavigationDecision.VISIBLE
                if placement.discoverable
                else NavigationDecision.HIDDEN
            ),
            reason="This route is available.",
            required_mode=(
                NavigationMode.ADVANCED if placement.advanced_only else None
            ),
            fallback_route_id=fallback_route_id,
            search_visible=placement.discoverable,
            direct_link_behavior=DirectLinkBehavior.ALLOW,
            is_favorite=is_favorite,
        )


def validate_navigation_policy() -> list[str]:
    """Return errors when a registered route lacks a valid policy outcome."""
    errors = validate_destinations()
    contexts = (
        NavigationContext(),
        NavigationContext(
            fedora_variant=FedoraVariant.ATOMIC,
            capabilities=frozenset({"rpm-ostree"}),
        ),
        NavigationContext(
            mode=NavigationMode.ADVANCED,
        ),
        NavigationContext(
            mode=NavigationMode.ADVANCED,
            fedora_variant=FedoraVariant.ATOMIC,
            capabilities=frozenset({"rpm-ostree"}),
        ),
    )
    for route in all_routes():
        for context in contexts:
            result = NavigationPolicy.evaluate(route.id, context)
            if result.route_id != route.id:
                errors.append(f"route {route.id} has no stable policy outcome")
    return errors
