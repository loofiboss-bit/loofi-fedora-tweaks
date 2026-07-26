"""Responsive section-navigation host for stable route IDs."""

from __future__ import annotations

from dataclasses import dataclass

from core.navigation import (
    Destination,
    NavigationContext,
    NavigationDecision,
    NavigationPolicy,
    NavigationPolicyResult,
    get_route,
    placement_for_route,
    sections_for_destination,
)
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout

from ui.components.navigation import SectionItem, SectionNavigator


@dataclass(frozen=True)
class SecondaryRoute:
    """One visible section entry in the shared secondary navigation."""

    section_id: str
    route_id: str
    label: str
    description: str
    icon: str = ""
    group: str = ""


_SPECIALIST_GROUPS = {
    "performance_tuning": "Performance & gaming",
    "gaming": "Performance & gaming",
    "development": "Development & local AI",
    "developer_tools": "Development & local AI",
    "ai_lab": "Development & local AI",
    "ai_lab_voice": "Development & local AI",
    "ai_lab_knowledge": "Development & local AI",
    "profiles": "Profiles & extensions",
    "extensions": "Profiles & extensions",
    "community": "Profiles & extensions",
    "community_marketplace": "Profiles & extensions",
    "community_plugins": "Profiles & extensions",
    "community_featured": "Profiles & extensions",
    "loofi_link": "Devices & sharing",
    "loofi_link_clipboard": "Devices & sharing",
    "loofi_link_file_drop": "Devices & sharing",
    "agents": "Agents & automation",
    "agents_list": "Agents & automation",
    "agents_create": "Agents & automation",
    "agents_activity": "Agents & automation",
    "automation": "Agents & automation",
    "automation_replicator": "Agents & automation",
    "state_teleport": "Agents & automation",
    "virtualization": "Virtualization",
    "virtualization_gpu": "Virtualization",
    "virtualization_disposable": "Virtualization",
}
_SPECIALIST_GROUP_ORDER = (
    "Performance & gaming",
    "Development & local AI",
    "Profiles & extensions",
    "Devices & sharing",
    "Agents & automation",
    "Virtualization",
    "Other specialist tools",
)


def specialist_group_for_section(section_id: str) -> str:
    """Return user-facing grouping for a Specialist Tools section."""
    return _SPECIALIST_GROUPS.get(str(section_id), "Other specialist tools")


def secondary_routes_for_destination(
    destination: Destination,
    context: NavigationContext,
) -> tuple[SecondaryRoute, ...]:
    """Return one visible canonical route per destination section."""
    routes: list[SecondaryRoute] = []
    for section in sections_for_destination(destination.id):
        route_ids = (section.default_route_id,) + tuple(
            route_id
            for route_id in destination.route_ids
            if route_id != section.default_route_id
            and _route_belongs_to_section(route_id, section.id)
        )
        visible_route_id = ""
        for route_id in route_ids:
            result = NavigationPolicy.evaluate(route_id, context)
            if result.decision is NavigationDecision.VISIBLE:
                visible_route_id = route_id
                break
        if not visible_route_id:
            continue
        route = get_route(visible_route_id)
        if route is None:
            continue
        routes.append(
            SecondaryRoute(
                section_id=section.id,
                route_id=route.id,
                label=section.label,
                description=section.description,
                icon=section.icon,
                group=(
                    specialist_group_for_section(section.id)
                    if destination.id == "advanced"
                    else ""
                ),
            )
        )
    if destination.id == "advanced":
        order = {
            group: index for index, group in enumerate(_SPECIALIST_GROUP_ORDER)
        }
        routes.sort(key=lambda route: order.get(route.group, len(order)))
    return tuple(routes)


def _route_belongs_to_section(route_id: str, section_id: str) -> bool:
    placement = placement_for_route(route_id)
    return placement is not None and placement.section_id == section_id


class DestinationHost(QFrame):
    """Single secondary-navigation component shared by every destination."""

    routeRequested = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._routes: tuple[SecondaryRoute, ...] = ()
        self._suppress_signal = False
        self.setObjectName("destinationHost")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(6)

        self.navigator = SectionNavigator(self)
        self.navigator.sectionActivated.connect(self._on_section_activated)
        layout.addWidget(self.navigator)

        self.explanation = QLabel(self)
        self.explanation.setObjectName("navigationExplanation")
        self.explanation.setWordWrap(True)
        self.explanation.setAccessibleName(self.tr("Navigation availability"))
        self.explanation.hide()
        layout.addWidget(self.explanation)

        self.hide()

    def set_destination(
        self,
        destination: Destination,
        context: NavigationContext,
        active_route_id: str = "",
    ) -> None:
        """Populate the shared section bar from policy-approved routes."""
        self._suppress_signal = True
        self._routes = secondary_routes_for_destination(destination, context)
        self.navigator.set_filtering_enabled(destination.id == "advanced")
        self.navigator.set_sections(
            [
                SectionItem(
                    section_id=route.section_id,
                    label=route.label,
                    description=route.description,
                    icon=route.icon,
                    group=route.group,
                )
                for route in self._routes
            ]
        )
        self._suppress_signal = False
        self.clear_explanation()
        self.set_active_route(active_route_id or destination.default_route_id)
        self.setVisible(len(self._routes) > 1)

    def route_ids(self) -> tuple[str, ...]:
        return tuple(route.route_id for route in self._routes)

    def set_active_route(self, route_id: str) -> None:
        """Select the section containing a route without requesting navigation."""
        placement = placement_for_route(route_id)
        if placement is None:
            return
        self._suppress_signal = True
        self.navigator.set_active_section(placement.section_id)
        self._suppress_signal = False

    def set_compact(self, compact: bool) -> None:
        """Select full-label rail or narrow selector presentation."""
        self.navigator.set_compact(compact)

    def is_compact(self) -> bool:
        return self.navigator.is_compact()

    def refresh_icon_tints(self) -> None:
        """Refresh section icons after the semantic palette changes."""
        self.navigator.refresh_icons()

    def show_policy_result(self, result: NavigationPolicyResult) -> None:
        """Show a compact safe explanation for gated or unavailable deep links."""
        self.explanation.setText(result.reason)
        self.explanation.show()
        self.show()

    def clear_explanation(self) -> None:
        self.explanation.clear()
        self.explanation.hide()

    def _on_section_activated(self, section_id: str) -> None:
        if self._suppress_signal:
            return
        for route in self._routes:
            if route.section_id == section_id:
                self.routeRequested.emit(route.route_id)
                return
