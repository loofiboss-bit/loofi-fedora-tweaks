"""Policy-backed global discovery for routes, settings, and safe action entry points.

The model is intentionally PyQt-free.  Search results describe where the UI
should navigate; they never carry executable callbacks or command vectors.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum

from .destinations import get_destination
from .manifest import NavigationRoute, all_routes, resolve
from .models import FedoraVariant, NavigationContext, NavigationDecision
from .policy import NavigationPolicy


class SearchFilter(Enum):
    """Discovery scopes exposed by the shared global-search surface."""

    ALL = "all"
    ACTIONS = "actions"


class SearchResultKind(Enum):
    """User-facing result types owned by the global search model."""

    ROUTE = "route"
    SETTING = "setting"
    ACTION = "action"


@dataclass(frozen=True)
class SearchResult:
    """One policy-approved discovery result with navigation-only activation."""

    id: str
    label: str
    description: str
    kind: SearchResultKind
    route_id: str
    destination_id: str
    destination_label: str
    keywords: tuple[str, ...] = ()
    risk: str = "none"
    action_id: str | None = None
    pinned: bool = False
    suggested: bool = False


@dataclass(frozen=True)
class _ActionDefinition:
    id: str
    label: str
    description: str
    route_id: str
    keywords: tuple[str, ...]
    risk: str
    action_id: str | None = None
    allowed_variants: frozenset[FedoraVariant] = frozenset(
        {FedoraVariant.TRADITIONAL, FedoraVariant.ATOMIC}
    )
    required_capabilities: frozenset[str] = frozenset()


_ACTION_CENTER_ACTIONS: tuple[_ActionDefinition, ...] = (
    _ActionDefinition(
        id="action-center:dnf-clean-all",
        label="Clean package metadata cache",
        description="Open Action Center to review and plan Traditional Fedora cache cleanup.",
        route_id="maintenance:action-center",
        keywords=("dnf", "dnf5", "cache", "metadata", "cleanup"),
        risk="low",
        action_id="dnf-clean-all",
        allowed_variants=frozenset({FedoraVariant.TRADITIONAL}),
        required_capabilities=frozenset({"dnf"}),
    ),
    _ActionDefinition(
        id="action-center:restart-failed-service",
        label="Restart a failed service",
        description="Open Action Center to select, review, and plan a failed-service restart.",
        route_id="maintenance:action-center",
        keywords=("systemd", "service", "failed", "restart"),
        risk="medium",
        action_id="restart-failed-service",
    ),
    _ActionDefinition(
        id="action-center:fstrim-all",
        label="Trim supported filesystems",
        description="Open Action Center to review storage support and plan filesystem trim.",
        route_id="maintenance:action-center",
        keywords=("fstrim", "ssd", "discard", "storage"),
        risk="low",
        action_id="fstrim-all",
    ),
)


class GlobalSearchModel:
    """Build and query the single policy-backed application discovery index."""

    def __init__(
        self,
        context: NavigationContext | None = None,
        *,
        configured_quick_actions: object = (),
    ) -> None:
        self._context = context or NavigationContext()
        self._configured_quick_actions = configured_quick_actions
        self._results = self._build_results()

    def all_results(
        self,
        search_filter: SearchFilter = SearchFilter.ALL,
    ) -> tuple[SearchResult, ...]:
        """Return the complete policy-approved index for one discovery scope."""
        if search_filter is SearchFilter.ACTIONS:
            return tuple(
                result
                for result in self._results
                if result.kind is SearchResultKind.ACTION
            )
        return self._results

    def search(
        self,
        query: str = "",
        *,
        search_filter: SearchFilter = SearchFilter.ALL,
        limit: int | None = None,
    ) -> tuple[SearchResult, ...]:
        """Return deterministic relevance-ranked results for ``query``."""
        candidates = self.all_results(search_filter)
        normalized_query = " ".join(str(query or "").casefold().split())
        scored: list[tuple[int, SearchResult]] = []
        for result in candidates:
            score = self._score(result, normalized_query)
            if score > 0:
                scored.append((score, result))
        scored.sort(
            key=lambda item: (
                -item[0],
                not item[1].pinned,
                not item[1].suggested,
                item[1].label.casefold(),
                item[1].id,
            )
        )
        results = tuple(result for _score, result in scored)
        if limit is not None:
            return results[: max(0, int(limit))]
        return results

    def _build_results(self) -> tuple[SearchResult, ...]:
        results: list[SearchResult] = []
        results.extend(self._route_results())
        results.extend(self._configured_action_results())
        results.extend(self._action_center_results())
        return tuple(results)

    def _route_results(self) -> Iterable[SearchResult]:
        for route in all_routes():
            policy = NavigationPolicy.evaluate(route.id, self._context)
            if (
                policy.decision is not NavigationDecision.VISIBLE
                or not policy.search_visible
            ):
                continue
            kind = (
                SearchResultKind.SETTING
                if route.id == "settings" or route.id.startswith("settings:")
                else SearchResultKind.ROUTE
            )
            yield self._result_for_route(
                result_id=f"{kind.value}:{route.id}",
                label=route.label,
                description=route.description,
                kind=kind,
                route=route,
                keywords=tuple(route.keywords) + tuple(route.aliases),
                risk=route.risk,
                pinned=policy.is_favorite,
            )

    def _configured_action_results(self) -> Iterable[SearchResult]:
        actions = self._configured_quick_actions
        if isinstance(actions, (str, bytes)) or not isinstance(actions, Iterable):
            return
        seen: set[str] = set()
        for raw_action in actions:
            if not isinstance(raw_action, Mapping):
                continue
            route = resolve(str(raw_action.get("route_id") or raw_action.get("target_tab") or ""))
            if route is None:
                continue
            policy = NavigationPolicy.evaluate(route.id, self._context)
            if (
                policy.decision is not NavigationDecision.VISIBLE
                or not policy.search_visible
            ):
                continue
            action_key = str(raw_action.get("id") or route.id).strip() or route.id
            result_id = f"configured-action:{action_key}"
            if result_id in seen:
                continue
            seen.add(result_id)
            label = str(raw_action.get("label") or route.label).strip() or route.label
            yield self._result_for_route(
                result_id=result_id,
                label=label,
                description=f"Open {route.label} to review this task.",
                kind=SearchResultKind.ACTION,
                route=route,
                keywords=tuple(route.keywords) + (action_key,),
                risk=route.risk,
                pinned=policy.is_favorite,
                suggested=True,
            )

    def _action_center_results(self) -> Iterable[SearchResult]:
        for definition in _ACTION_CENTER_ACTIONS:
            if self._context.fedora_variant not in definition.allowed_variants:
                continue
            if not definition.required_capabilities.issubset(
                self._context.capabilities
            ):
                continue
            route = resolve(definition.route_id)
            if route is None:
                continue
            policy = NavigationPolicy.evaluate(route.id, self._context)
            if (
                policy.decision is not NavigationDecision.VISIBLE
                or not policy.search_visible
            ):
                continue
            yield self._result_for_route(
                result_id=definition.id,
                label=definition.label,
                description=definition.description,
                kind=SearchResultKind.ACTION,
                route=route,
                keywords=definition.keywords,
                risk=definition.risk,
                action_id=definition.action_id,
                pinned=policy.is_favorite,
            )

    def _result_for_route(
        self,
        *,
        result_id: str,
        label: str,
        description: str,
        kind: SearchResultKind,
        route: NavigationRoute,
        keywords: tuple[str, ...],
        risk: str,
        action_id: str | None = None,
        pinned: bool = False,
        suggested: bool = False,
    ) -> SearchResult:
        policy = NavigationPolicy.evaluate(route.id, self._context)
        destination = get_destination(policy.destination_id)
        return SearchResult(
            id=result_id,
            label=label,
            description=description,
            kind=kind,
            route_id=route.id,
            destination_id=policy.destination_id,
            destination_label=(
                destination.label if destination is not None else route.category
            ),
            keywords=keywords,
            risk=risk,
            action_id=action_id,
            pinned=pinned,
            suggested=suggested,
        )

    @staticmethod
    def _score(result: SearchResult, query: str) -> int:
        priority = (20 if result.pinned else 0) + (10 if result.suggested else 0)
        if not query:
            return 1 + priority
        label = result.label.casefold()
        destination = result.destination_label.casefold()
        description = result.description.casefold()
        if label == query:
            return 120 + priority
        if label.startswith(query):
            return 100 + priority
        if query in label:
            return 80 + priority
        if destination.startswith(query):
            return 60 + priority
        if query in destination:
            return 50 + priority
        if any(query in keyword.casefold() for keyword in result.keywords):
            return 40 + priority
        if query in description:
            return 20 + priority
        return 0
