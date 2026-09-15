"""Navigation-safe discovery for the v29 utility task catalog."""

from __future__ import annotations

from typing import Any

from core.tasks import TaskArea, TaskCatalog, TaskContext, TaskSearchResult

from .task_routes import TASK_ROUTE_REDIRECTS, TASK_ROUTE_RECORDS


def utility_routes() -> tuple[dict[str, Any], ...]:
    """Return the six v29 landing-surface records in display order."""
    return TASK_ROUTE_RECORDS


def utility_route_redirect(route_id: str) -> str | None:
    """Return the v29 destination for one legacy deep link, if applicable."""
    return TASK_ROUTE_REDIRECTS.get(str(route_id))


def canonical_utility_route(route_id: str) -> str:
    """Map legacy Changes/Action Center links to Activity safely."""
    value = str(route_id or "").strip()
    return TASK_ROUTE_REDIRECTS.get(value, value)


def search_utility_tasks(
    query: str = "",
    *,
    area: TaskArea | str | None = None,
    context: TaskContext | None = None,
    include_guidance: bool = True,
    include_unavailable: bool = True,
    limit: int | None = None,
) -> tuple[TaskSearchResult, ...]:
    """Return deterministic task results with guidance marked non-runnable."""
    return TaskCatalog().search_results(
        query,
        area=area,
        context=context,
        include_guidance=include_guidance,
        include_unavailable=include_unavailable,
        limit=limit,
    )


__all__ = [
    "canonical_utility_route",
    "search_utility_tasks",
    "utility_route_redirect",
    "utility_routes",
]
