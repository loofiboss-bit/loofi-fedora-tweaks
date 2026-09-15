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
from core.actions.catalog import ActionCatalog
from core.tasks import TaskArea, TaskCatalog, TaskContext, TaskExecutionMode


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
    # Product-task metadata is optional so persisted v15 route/action results
    # remain byte-for-byte compatible. A task result is still navigation only;
    # the task ID lets the owning landing page focus the requested card.
    task_id: str | None = None
    availability: str = ""
    manual_only: bool = False


_ACTION_ALIASES: dict[str, tuple[str, ...]] = {
    "dnf-clean-all": ("free disk space", "cleanup", "cache"),
    "fstrim-all": ("free disk space", "ssd", "storage"),
    "autoremove-packages": ("free disk space", "unused packages", "cleanup"),
    "vacuum-journal": ("free disk space", "cleanup", "logs"),
    "update-fedora-system": ("updates", "update", "system"),
    "update-flatpaks": ("updates", "update", "flatpak"),
    "update-firmware": ("updates", "update", "firmware"),
    "restart-failed-service": ("slow system", "slow", "service", "system"),
}


class GlobalSearchModel:
    """Build and query the single policy-backed application discovery index."""

    def __init__(
        self,
        context: NavigationContext | None = None,
        *,
        configured_quick_actions: object = (),
    ) -> None:
        # A context-free model is retained as an inert compatibility adapter
        # for the legacy command-palette constructor.  Live shell callers pass
        # the detected NavigationContext explicitly, which is the only safe
        # point at which v29 task discovery may be projected.
        context_provided = context is not None
        self._context = context or NavigationContext()
        self._configured_quick_actions = configured_quick_actions
        self._results = self._build_results()
        self._task_results = self._build_task_results() if context_provided else ()

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
        # Keep the existing route/action index intact while adding the v29
        # goal-oriented projection. Task entries use the normal route kind,
        # so older consumers that only understand routes remain compatible.
        return (*self._results, *self._task_results)

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

    def _build_task_results(self) -> tuple[SearchResult, ...]:
        """Project the canonical v29 task catalog into navigation results.

        Task metadata never includes command vectors or callbacks. The result
        only carries a stable task ID and owning landing route; the shell
        resolves the descriptor again before focusing the card.
        """
        catalog = TaskCatalog()
        context = TaskContext.from_navigation_context(self._context)
        destination_labels = {
            "home": "Home",
            "install": "Install",
            "tune": "Tune",
            "fix": "Fix",
            "update": "Update",
            "activity": "Activity & Recovery",
        }
        results: list[SearchResult] = []
        for descriptor in catalog.all():
            if not descriptor.discoverable:
                continue
            # ``TaskDescriptor`` accepts a string for readable deserialization;
            # its runtime contract normalizes the value to ``TaskArea``. Keep
            # the local narrowing explicit for mypy and older callers.
            area_value = (
                descriptor.area.value
                if isinstance(descriptor.area, TaskArea)
                else str(descriptor.area)
            )
            eligibility = catalog.eligibility(descriptor, context)
            # Action mode remains an audited action review surface. v29 task
            # discovery belongs to ordinary goal search and never duplicates
            # the privileged action list there.
            kind = (
                SearchResultKind.SETTING
                if descriptor.execution_mode is TaskExecutionMode.HANDOFF
                else SearchResultKind.ROUTE
            )
            status = eligibility.status.replace("_", " ")
            description = descriptor.description
            if status not in {"supported", "read only", "native handoff"}:
                description = f"{description} ({status.title()})"
            results.append(
                SearchResult(
                    id=f"task:{descriptor.id}",
                    label=descriptor.title,
                    description=description,
                    kind=kind,
                    route_id=descriptor.route_id,
                    destination_id=area_value,
                    destination_label=destination_labels.get(
                        area_value,
                        area_value.title(),
                    ) or area_value.title(),
                    keywords=(
                        descriptor.id,
                        descriptor.goal,
                        descriptor.group,
                        *descriptor.keywords,
                    ),
                    risk=descriptor.risk,
                    task_id=descriptor.id,
                    availability=eligibility.status,
                    manual_only=descriptor.manual_only,
                )
            )
        return tuple(results)

    def task_results(self) -> tuple[SearchResult, ...]:
        """Return only the v29 task projection for consumers that need it."""
        return self._task_results

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
        route = resolve("maintenance:action-center")
        if route is None:
            return
        for definition in ActionCatalog().list():
            if definition.operation_class == "manual_only":
                continue
            allowed_variants = frozenset(
                FedoraVariant(value)
                for value in definition.supported_variants
                if value in {item.value for item in FedoraVariant}
            )
            if self._context.fedora_variant not in allowed_variants:
                continue
            required_capabilities: frozenset[str] = frozenset()
            if allowed_variants == frozenset({FedoraVariant.TRADITIONAL}):
                required_capabilities = frozenset({"dnf5"})
            elif allowed_variants == frozenset({FedoraVariant.ATOMIC}):
                required_capabilities = frozenset({"rpm-ostree"})
            if not required_capabilities.issubset(self._context.capabilities):
                continue
            policy = NavigationPolicy.evaluate(route.id, self._context)
            if (
                policy.decision is not NavigationDecision.VISIBLE
                or not policy.search_visible
            ):
                continue
            yield self._result_for_route(
                result_id=f"action-center:{definition.id}",
                label=definition.title,
                description=f"Inspect or run through Action Center: {definition.description.lower()}",
                kind=SearchResultKind.ACTION,
                route=route,
                keywords=(
                    definition.id,
                    definition.capability_id,
                    definition.title,
                    definition.description,
                    *_ACTION_ALIASES.get(definition.id, ()),
                ),
                risk=str(getattr(definition.risk_level, "value", definition.risk_level)),
                action_id=definition.id,
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
        tokens = tuple(token for token in query.casefold().split() if token)
        fields = (
            result.label.casefold(),
            result.destination_label.casefold(),
            result.description.casefold(),
            *(keyword.casefold() for keyword in result.keywords),
        )
        if not all(any(token in field for field in fields) for token in tokens):
            return 0
        if len(tokens) > 1:
            phrase = " ".join(tokens)
            if phrase in result.label.casefold():
                return 120 + priority
            if phrase in result.description.casefold():
                return 80 + priority
            return 60 + sum(5 for token in tokens if token in result.label.casefold()) + priority
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
