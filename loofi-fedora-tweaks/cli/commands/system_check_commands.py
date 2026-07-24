"""Read-only System Check CLI presentation helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def handle_health_comparison(
    *,
    json_output: bool,
    output_json: Callable[[dict[str, Any]], Any],
    print_fn: Callable[[str], Any],
) -> int:
    """Render the latest persisted before/after comparison."""
    from core.observability import HealthTimelineStore
    from core.system_check.comparison import (
        COMPARISON_SCHEMA_ID,
        COMPARISON_SCHEMA_VERSION,
        latest_comparison,
    )

    comparison = latest_comparison(HealthTimelineStore().load())
    payload = {
        "schema_id": COMPARISON_SCHEMA_ID,
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "command": "comparison",
        "data": {
            "comparison": (
                comparison.to_dict()
                if comparison is not None
                else None
            )
        },
    }
    if json_output:
        output_json(payload)
    elif comparison is None:
        print_fn("No two compatible saved System Checks are available.")
    else:
        print_fn(
            f"System Check comparison: {comparison.before_check_id} "
            f"-> {comparison.after_check_id}"
        )
        for outcome in comparison.outcomes:
            print_fn(
                f"- [{outcome.state}] {outcome.title}: "
                f"{outcome.reason_code}"
            )
    return 0
