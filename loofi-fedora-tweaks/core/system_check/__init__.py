"""Canonical read-only System Check domain contracts."""

from importlib import import_module
from typing import Any

from core.system_check.comparison import (
    FindingOutcome,
    SystemCheckComparison,
    comparison_from_check,
    compare_results,
    latest_comparison,
    results_from_snapshots,
)
from core.system_check.models import CheckProgress, CheckSourceError, FindingEvidence, SystemCheckResult, SystemFinding

_LAZY_EXPORTS = {
    "FindingActionHandoff": ("core.system_check.handoff", "FindingActionHandoff"),
    "FindingActionReview": ("core.system_check.handoff", "FindingActionReview"),
    "FindingHandoffError": ("core.system_check.handoff", "FindingHandoffError"),
    "FindingView": ("core.system_check.presentation", "FindingView"),
    "HistoryView": ("core.system_check.presentation", "HistoryView"),
    "MaintenanceOutcomeView": (
        "core.system_check.presentation",
        "MaintenanceOutcomeView",
    ),
    "MetricView": ("core.system_check.presentation", "MetricView"),
    "SystemCheckPageState": (
        "core.system_check.presentation",
        "SystemCheckPageState",
    ),
    "SystemCheckPresentationService": (
        "core.system_check.presentation",
        "SystemCheckPresentationService",
    ),
}


def __getattr__(name: str) -> Any:
    """Keep compatibility exports lazy so the domain package stays PyQt-free."""
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attribute = target
    value = getattr(import_module(module_name), attribute)
    globals()[name] = value
    return value


__all__ = [
    "CheckProgress",
    "CheckSourceError",
    "FindingEvidence",
    "FindingActionHandoff",
    "FindingActionReview",
    "FindingHandoffError",
    "FindingOutcome",
    "FindingView",
    "HistoryView",
    "MaintenanceOutcomeView",
    "MetricView",
    "SystemCheckPageState",
    "SystemCheckPresentationService",
    "SystemCheckResult",
    "SystemCheckComparison",
    "SystemFinding",
    "comparison_from_check",
    "compare_results",
    "latest_comparison",
    "results_from_snapshots",
]
