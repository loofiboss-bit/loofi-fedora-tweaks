"""Unified Action Center primitives for previewable system actions."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_ACTION_EXPORTS = {
    "ActionCatalog": ("core.actions.catalog", "ActionCatalog"),
    "SystemActionRuntime": ("core.actions.catalog", "SystemActionRuntime"),
    "ActionDefinition": ("core.actions.contracts", "ActionDefinition"),
    "ActionLifecycleError": ("core.actions.contracts", "ActionLifecycleError"),
    "ActionPlan": ("core.actions.contracts", "ActionPlan"),
    "ActionRun": ("core.actions.contracts", "ActionRun"),
    "FindingContext": ("core.actions.contracts", "FindingContext"),
    "PolicyDecision": ("core.actions.contracts", "PolicyDecision"),
    "PreparedActionRun": ("core.actions.contracts", "PreparedActionRun"),
    "VerificationDecision": ("core.actions.contracts", "VerificationDecision"),
    "ActionCenterItem": ("core.actions.model", "ActionCenterItem"),
    "ActionRisk": ("core.actions.model", "ActionRisk"),
    "ActionState": ("core.actions.model", "ActionState"),
    "RollbackGuidance": ("core.actions.model", "RollbackGuidance"),
    "ActionCenterService": ("core.actions.center", "ActionCenterService"),
    "ActionCenterBusyError": ("core.actions.orchestrator", "ActionCenterBusyError"),
    "ActionCenterError": ("core.actions.orchestrator", "ActionCenterError"),
    "ActionCenterOrchestrator": ("core.actions.orchestrator", "ActionCenterOrchestrator"),
    "ActionPlanIntegrityError": ("core.actions.orchestrator", "ActionPlanIntegrityError"),
    "ActionPlanNotFoundError": ("core.actions.orchestrator", "ActionPlanNotFoundError"),
    "ActionPlanRejectedError": ("core.actions.orchestrator", "ActionPlanRejectedError"),
    "ActionRunNotFoundError": ("core.actions.orchestrator", "ActionRunNotFoundError"),
    "ActionHistoryStore": ("core.actions.history", "ActionHistoryStore"),
    "ActionQueue": ("core.actions.queue", "ActionQueue"),
    "RollbackGuidanceService": ("core.actions.rollback", "RollbackGuidanceService"),
    "ActionPlanStore": ("core.actions.stores", "ActionPlanStore"),
    "ActionRunStore": ("core.actions.stores", "ActionRunStore"),
    "ActionStoreVersionError": ("core.actions.stores", "ActionStoreVersionError"),
    "EligibilityDecision": ("core.actions.eligibility", "EligibilityDecision"),
    "audit_definitions": ("core.actions.eligibility", "audit_definitions"),
    "classify_definition": ("core.actions.eligibility", "classify_definition"),
    "DirectActionResult": ("core.actions.direct", "DirectActionResult"),
    "DirectActionService": ("core.actions.direct", "DirectActionService"),
    "EvidenceFact": ("core.actions.outcomes", "EvidenceFact"),
    "OutcomeEvidenceComposer": ("core.actions.outcomes", "OutcomeEvidenceComposer"),
    "OutcomeSummary": ("core.actions.outcomes", "OutcomeSummary"),
    "RecoveryReadiness": ("core.actions.outcomes", "RecoveryReadiness"),
}

__all__ = tuple(sorted(_ACTION_EXPORTS))


def __getattr__(name: str) -> Any:
    """Lazily import Action Center symbols on first access."""
    location = _ACTION_EXPORTS.get(name)
    if location is None:
        raise AttributeError(name)
    module_name, attr_name = location
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
