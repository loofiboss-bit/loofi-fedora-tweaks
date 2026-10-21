"""Human-readable scope for the exact dependency transaction being approved."""
from __future__ import annotations

from typing import Any, Callable

from services.software.rpm_transactions import preview_from_facts


def rpm_review_lines(payload: Any, translate: Callable[[str], str]) -> tuple[str, tuple[str, ...]]:
    snapshot = preview_from_facts(payload)
    lines = [translate("System RPM transaction. Application data is preserved."),
             translate("Requested packages: %1").replace("%1", ", ".join(snapshot.packages))]
    for item in snapshot.operations:
        lines.append(translate("%1: %2 — source %3").replace("%1", translate(item["action"]))
                     .replace("%2", item["nevra"]).replace("%3", item["repo_id"]))
    lines.append(translate("Changed packages, dependencies or sources require a fresh review."))
    return "\n".join(lines), (translate("Approved transaction digest: %1").replace("%1", snapshot.digest),)
