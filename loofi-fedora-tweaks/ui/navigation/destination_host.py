"""Shared secondary navigation host for stable v15 route IDs."""

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
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QLabel, QTabBar, QVBoxLayout


@dataclass(frozen=True)
class SecondaryRoute:
    """One visible section entry in the shared secondary navigation."""

    section_id: str
    route_id: str
    label: str
    description: str


def secondary_routes_for_destination(
    destination: Destination,
    context: NavigationContext,
) -> tuple[SecondaryRoute, ...]:
    """Return one visible canonical route per destination section."""
    visible_by_section: dict[str, SecondaryRoute] = {}
    ordered_route_ids = (destination.default_route_id,) + tuple(
        route_id
        for route_id in destination.route_ids
        if route_id != destination.default_route_id
    )
    for route_id in ordered_route_ids:
        route = get_route(route_id)
        placement = placement_for_route(route_id)
        if route is None or placement is None:
            continue
        result = NavigationPolicy.evaluate(route_id, context)
        if result.decision is not NavigationDecision.VISIBLE:
            continue
        visible_by_section.setdefault(
            placement.section_id,
            SecondaryRoute(
                section_id=placement.section_id,
                route_id=route.id,
                label=route.label,
                description=route.description,
            ),
        )
    return tuple(visible_by_section.values())


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

        self.tabs = QTabBar(self)
        self.tabs.setObjectName("secondaryNavigation")
        self.tabs.setAccessibleName(self.tr("Sections"))
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(False)
        self.tabs.setExpanding(False)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setElideMode(Qt.TextElideMode.ElideRight)
        self.tabs.setMinimumHeight(max(36, int(self.fontMetrics().height() * 2.2)))
        self.tabs.currentChanged.connect(self._on_current_changed)
        layout.addWidget(self.tabs)

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
        while self.tabs.count():
            self.tabs.removeTab(0)
        self._routes = secondary_routes_for_destination(destination, context)
        for route in self._routes:
            index = self.tabs.addTab(route.label)
            self.tabs.setTabData(index, route.route_id)
            self.tabs.setTabToolTip(index, route.description or route.label)
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
        for index, route in enumerate(self._routes):
            if route.section_id == placement.section_id:
                self.tabs.setCurrentIndex(index)
                break
        self._suppress_signal = False

    def show_policy_result(self, result: NavigationPolicyResult) -> None:
        """Show a compact safe explanation for gated or unavailable deep links."""
        self.explanation.setText(result.reason)
        self.explanation.show()
        self.show()

    def clear_explanation(self) -> None:
        self.explanation.clear()
        self.explanation.hide()

    def _on_current_changed(self, index: int) -> None:
        if self._suppress_signal or index < 0:
            return
        route_id = self.tabs.tabData(index)
        if route_id:
            self.routeRequested.emit(str(route_id))
