"""Compatibility destination views generated from the canonical v18 catalog."""

from __future__ import annotations

from collections import Counter

from core.product_catalog import (
    catalog_destinations,
    catalog_placements,
    catalog_sections,
)

from .manifest import all_routes, get_route
from .models import Destination, NavigationMode, RoutePlacement, SectionDefinition

_PLACEMENTS = catalog_placements()
_SECTIONS = catalog_sections()
_DESTINATIONS = catalog_destinations()
_PLACEMENT_BY_ROUTE = {placement.route_id: placement for placement in _PLACEMENTS}
_SECTION_BY_DESTINATION_AND_ID = {
    (section.destination_id, section.id): section for section in _SECTIONS
}
_DESTINATION_BY_ID = {destination.id: destination for destination in _DESTINATIONS}

STANDARD_DESTINATIONS = tuple(item for item in _DESTINATIONS if not item.advanced_only)
ADVANCED_DESTINATION = next(item for item in _DESTINATIONS if item.advanced_only)


def all_destinations() -> tuple[Destination, ...]:
    """Return all destination definitions, including Advanced."""
    return _DESTINATIONS


def destinations_for_mode(mode: NavigationMode) -> tuple[Destination, ...]:
    """Return standard destinations and optional Advanced destination."""
    if mode is NavigationMode.ADVANCED:
        return _DESTINATIONS
    return STANDARD_DESTINATIONS


def get_destination(destination_id: str) -> Destination | None:
    return _DESTINATION_BY_ID.get(str(destination_id))


def placement_for_route(route_id: str) -> RoutePlacement | None:
    return _PLACEMENT_BY_ROUTE.get(str(route_id))


def sections_for_destination(destination_id: str) -> tuple[SectionDefinition, ...]:
    return tuple(
        sorted(
            (section for section in _SECTIONS if section.destination_id == str(destination_id)),
            key=lambda section: section.order,
        )
    )


def get_section(destination_id: str, section_id: str) -> SectionDefinition | None:
    return _SECTION_BY_DESTINATION_AND_ID.get((str(destination_id), str(section_id)))


def validate_destinations() -> list[str]:
    """Return relationship errors for the catalog-generated destination view."""
    errors: list[str] = []
    manifest_ids = {route.id for route in all_routes()}
    placement_ids = [placement.route_id for placement in _PLACEMENTS]

    for route_id, count in Counter(placement_ids).items():
        if count > 1:
            errors.append(f"route {route_id} has {count} destination placements")
    for route_id in sorted(manifest_ids - set(placement_ids)):
        errors.append(f"route {route_id} has no destination placement")
    for route_id in sorted(set(placement_ids) - manifest_ids):
        errors.append(f"placement references unknown route {route_id}")

    destination_ids = [destination.id for destination in _DESTINATIONS]
    for destination_id, count in Counter(destination_ids).items():
        if count > 1:
            errors.append(f"duplicate destination id: {destination_id}")

    for destination in _DESTINATIONS:
        if get_route(destination.default_route_id) is None:
            errors.append(f"destination {destination.id} has unknown default route {destination.default_route_id}")
        if destination.default_route_id not in destination.route_ids:
            errors.append(f"destination {destination.id} default route is outside the destination")

    for placement in _PLACEMENTS:
        placed_destination = get_destination(placement.destination_id)
        if placed_destination is None:
            errors.append(f"route {placement.route_id} references unknown destination {placement.destination_id}")
        elif placement.route_id not in placed_destination.route_ids:
            errors.append(f"route {placement.route_id} missing from destination {placement.destination_id}")
        if placement.redirect_route_id and get_route(placement.redirect_route_id) is None:
            errors.append(f"route {placement.route_id} redirects to unknown route {placement.redirect_route_id}")
        if get_section(placement.destination_id, placement.section_id) is None:
            errors.append(f"route {placement.route_id} references unknown section {placement.destination_id}:{placement.section_id}")

    for destination in _DESTINATIONS:
        sections = sections_for_destination(destination.id)
        section_ids = [section.id for section in sections]
        section_orders = [section.order for section in sections]
        for section_id, count in Counter(section_ids).items():
            if count > 1:
                errors.append(f"destination {destination.id} has duplicate section {section_id}")
        for order, count in Counter(section_orders).items():
            if count > 1:
                errors.append(f"destination {destination.id} has duplicate section order {order}")
        for section in sections:
            default_placement = placement_for_route(section.default_route_id)
            if default_placement is None:
                errors.append(f"section {destination.id}:{section.id} has unknown default route {section.default_route_id}")
            elif default_placement.destination_id != destination.id or default_placement.section_id != section.id:
                errors.append(f"section {destination.id}:{section.id} default route is outside the section")
            if not section.label or not section.icon:
                errors.append(f"section {destination.id}:{section.id} lacks presentation metadata")

    redirects = {
        placement.route_id: placement.redirect_route_id
        for placement in _PLACEMENTS
        if placement.redirect_route_id
    }
    for route_id, redirect_route_id in redirects.items():
        seen = {route_id}
        current = redirect_route_id
        while current in redirects:
            if current in seen:
                errors.append(f"route {route_id} has a redirect cycle")
                break
            seen.add(current)
            current = redirects[current]
    return errors
