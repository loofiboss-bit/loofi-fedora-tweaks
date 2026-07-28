"""Canonical product catalog and compatibility projections.

This module is the only runtime composer for built-in plugin, route,
destination, section, visibility, variant, capability, and risk metadata.
Legacy registries consume its immutable projections and never declare their
own product metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Mapping, cast

from core.catalog_models import (
    NativeHandoffId,
    Destination,
    FedoraVariant,
    NavigationRoute,
    PluginSpec,
    RoutePlacement,
    SectionDefinition,
)
from core.product_catalog_records import CATALOG_DATA

if TYPE_CHECKING:
    from core.plugins.metadata import PluginMetadata

RETIRED_ROUTE_REDIRECTS: Mapping[str, str] = MappingProxyType(
    {
        "community:marketplace": "community:presets",
        "community:plugins": "community:presets",
        "community:featured": "community:presets",
    }
)


@dataclass(frozen=True)
class ProductCatalogEntry:
    """Complete immutable identity and product policy for one stable route."""

    route: NavigationRoute
    plugin: PluginSpec
    placement: RoutePlacement
    section: SectionDefinition
    destination: Destination
    retired: bool = False
    compatibility_redirect: str | None = None

    @property
    def route_id(self) -> str:
        return self.route.id

    @property
    def plugin_id(self) -> str:
        return self.plugin.id

    @property
    def allowed_variants(self) -> frozenset[FedoraVariant]:
        return self.placement.allowed_variants


def _plugin(record: Mapping[str, Any]) -> PluginSpec:
    return PluginSpec(
        id=str(record["id"]),
        name=str(record["name"]),
        description=str(record["description"]),
        icon=str(record["icon"]),
        destination_id=str(record["destination_id"]),
        module=str(record["module"]),
        class_name=str(record["class_name"]),
        component=str(record["component"]),
        visibility=cast(Any, record["visibility"]),
        compat=cast(Mapping[str, Any], record["compat"]),
        category=str(record["category"]),
        badge=str(record["badge"]),
        order=int(record["order"]),
    )


def _route(record: Mapping[str, Any]) -> NavigationRoute:
    return NavigationRoute(
        id=str(record["id"]),
        label=str(record["label"]),
        plugin_id=str(record["plugin_id"]),
        category=str(record["category"]),
        icon=str(record["icon"]),
        description=str(record["description"]),
        aliases=tuple(str(value) for value in record["aliases"]),
        keywords=tuple(str(value) for value in record["keywords"]),
        risk=cast(Any, record["risk"]),
        visibility=cast(Any, record["visibility"]),
        subroute=str(record["subroute"]),
    )


def _placement(record: Mapping[str, Any]) -> RoutePlacement:
    return RoutePlacement(
        route_id=str(record["route_id"]),
        destination_id=str(record["destination_id"]),
        section_id=str(record["section_id"]),
        advanced_only=bool(record["advanced_only"]),
        component_id=str(record["component_id"]),
        required_capabilities=frozenset(str(value) for value in record["required_capabilities"]),
        allowed_variants=frozenset(FedoraVariant(str(value)) for value in record["allowed_variants"]),
        redirect_route_id=(str(record["redirect_route_id"]) if record["redirect_route_id"] is not None else None),
        discoverable=bool(record["discoverable"]),
        native_handoff_id=(
            NativeHandoffId(str(record["native_handoff_id"]))
            if record.get("native_handoff_id") is not None
            else None
        ),
    )


def _section(record: Mapping[str, Any]) -> SectionDefinition:
    return SectionDefinition(
        id=str(record["id"]),
        destination_id=str(record["destination_id"]),
        label=str(record["label"]),
        icon=str(record["icon"]),
        order=int(record["order"]),
        default_route_id=str(record["default_route_id"]),
        description=str(record["description"]),
    )


def _destination(record: Mapping[str, Any]) -> Destination:
    return Destination(
        id=str(record["id"]),
        label=str(record["label"]),
        icon=str(record["icon"]),
        default_route_id=str(record["default_route_id"]),
        route_ids=tuple(str(value) for value in record["route_ids"]),
        advanced_only=bool(record["advanced_only"]),
    )


_PLUGINS = tuple(_plugin(record) for record in CATALOG_DATA["plugins"])
_ROUTES = tuple(_route(record) for record in CATALOG_DATA["routes"])
_PLACEMENTS = tuple(_placement(record) for record in CATALOG_DATA["placements"])
_SECTIONS = tuple(_section(record) for record in CATALOG_DATA["sections"])
_DESTINATIONS = tuple(_destination(record) for record in CATALOG_DATA["destinations"])

_PLUGIN_BY_ID = MappingProxyType({item.id: item for item in _PLUGINS})
_PLACEMENT_BY_ROUTE = MappingProxyType({item.route_id: item for item in _PLACEMENTS})
_SECTION_BY_KEY = MappingProxyType({(item.destination_id, item.id): item for item in _SECTIONS})
_DESTINATION_BY_ID = MappingProxyType({item.id: item for item in _DESTINATIONS})


def catalog_routes() -> tuple[NavigationRoute, ...]:
    return _ROUTES


def catalog_plugins() -> tuple[PluginSpec, ...]:
    return _PLUGINS


def plugin_metadata_for_module(module_name: str) -> PluginMetadata:
    """Project legacy ``PluginMetadata`` for one catalog-owned UI module."""
    normalized = str(module_name).removeprefix("loofi-fedora-tweaks.")
    plugin = next((item for item in _PLUGINS if item.module == normalized), None)
    if plugin is None:
        raise LookupError(f"no product catalog plugin for module {module_name}")
    return plugin.metadata()


def catalog_placements() -> tuple[RoutePlacement, ...]:
    return _PLACEMENTS


def catalog_sections() -> tuple[SectionDefinition, ...]:
    return _SECTIONS


def catalog_destinations() -> tuple[Destination, ...]:
    return _DESTINATIONS


def product_catalog() -> tuple[ProductCatalogEntry, ...]:
    """Return the validated route-owned product catalog in stable order."""
    entries: list[ProductCatalogEntry] = []
    for route in _ROUTES:
        plugin = _PLUGIN_BY_ID.get(route.plugin_id)
        placement = _PLACEMENT_BY_ROUTE.get(route.id)
        if plugin is None or placement is None:
            continue
        section = _SECTION_BY_KEY.get((placement.destination_id, placement.section_id))
        destination = _DESTINATION_BY_ID.get(placement.destination_id)
        if section is None or destination is None:
            continue
        redirect = RETIRED_ROUTE_REDIRECTS.get(route.id)
        entries.append(
            ProductCatalogEntry(
                route=route,
                plugin=plugin,
                placement=placement,
                section=section,
                destination=destination,
                retired=redirect is not None,
                compatibility_redirect=redirect,
            )
        )
    return tuple(entries)


_ENTRY_BY_ROUTE = MappingProxyType({entry.route_id: entry for entry in product_catalog()})


def catalog_entry(route_id: str) -> ProductCatalogEntry | None:
    return _ENTRY_BY_ROUTE.get(str(route_id))


def validate_product_catalog() -> list[str]:
    """Return projection, uniqueness, relationship, and retirement drift."""
    errors: list[str] = []
    entry_ids = [entry.route_id for entry in product_catalog()]
    route_ids = [route.id for route in _ROUTES]
    plugin_ids = [plugin.id for plugin in _PLUGINS]
    destination_ids = [destination.id for destination in _DESTINATIONS]

    for label, values in (("route", route_ids), ("plugin", plugin_ids), ("destination", destination_ids)):
        for value in sorted({item for item in values if values.count(item) > 1}):
            errors.append(f"duplicate product catalog {label}: {value}")
    for route_id in sorted(set(route_ids) - set(entry_ids)):
        errors.append(f"route {route_id} has no complete product catalog entry")
    for entry in product_catalog():
        if entry.route.plugin_id != entry.plugin.id:
            errors.append(f"route {entry.route_id} plugin projection drifted")
        if entry.route_id not in entry.destination.route_ids:
            errors.append(f"route {entry.route_id} is outside destination {entry.destination.id}")
        if entry.section.destination_id != entry.destination.id:
            errors.append(f"route {entry.route_id} section is outside its destination")
        if entry.retired and entry.compatibility_redirect not in set(route_ids):
            errors.append(f"retired route {entry.route_id} has an invalid redirect")
    return errors
