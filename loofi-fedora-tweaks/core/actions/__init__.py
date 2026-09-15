"""Unified Action Center primitives for previewable system actions."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_ACTION_EXPORTS = {
    "ActionCatalog": ("core.actions.catalog", "ActionCatalog"),
    "ACTIVE_ACTION_IDS": ("core.actions.catalog", "ACTIVE_ACTION_IDS"),
    "SystemActionRuntime": ("core.actions.catalog", "SystemActionRuntime"),
    "ActionDefinition": ("core.actions.contracts", "ActionDefinition"),
    "InteractionPolicy": ("core.actions.contracts", "InteractionPolicy"),
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
    # v29 lifecycle and bundle contracts.  Keep imports lazy so importing the
    # package remains safe for CLI/read-only consumers without PyQt.
    "OperationController": ("core.actions.operation_controller", "OperationController"),
    "ActionOperationController": ("core.actions.operation_controller", "ActionOperationController"),
    "OperationControllerError": ("core.actions.operation_controller", "OperationControllerError"),
    "OperationNotPreparedError": ("core.actions.operation_controller", "OperationNotPreparedError"),
    "OperationConfirmationRequired": ("core.actions.operation_controller", "OperationConfirmationRequired"),
    "OperationEvent": ("core.actions.operation_controller", "OperationEvent"),
    "OperationOutcome": ("core.actions.operation_controller", "OperationOutcome"),
    "OperationResult": ("core.actions.operation_controller", "OperationResult"),
    "OperationTicket": ("core.actions.operation_controller", "OperationTicket"),
    "PreparedOperation": ("core.actions.operation_controller", "PreparedOperation"),
    "ActionBundle": ("core.actions.bundles", "ActionBundle"),
    "ActionBundleItem": ("core.actions.bundles", "ActionBundleItem"),
    "ActionBundleError": ("core.actions.bundles", "ActionBundleError"),
    "ActionBundleValidationError": ("core.actions.bundles", "ActionBundleValidationError"),
    "ActionBundleSchemaError": ("core.actions.bundles", "ActionBundleSchemaError"),
    "ActionBundleIntegrityError": ("core.actions.bundles", "ActionBundleIntegrityError"),
    "BundleValidationError": ("core.actions.bundles", "BundleValidationError"),
    "BundleSchemaError": ("core.actions.bundles", "BundleSchemaError"),
    "BundleIntegrityError": ("core.actions.bundles", "BundleIntegrityError"),
    "BundleItemResult": ("core.actions.bundles", "BundleItemResult"),
    "BundleOutcome": ("core.actions.bundles", "BundleOutcome"),
    "ActionBundleResult": ("core.actions.bundles", "ActionBundleResult"),
    "ActionChangeSet": ("core.actions.bundles", "ActionChangeSet"),
    "ActionChangeSetItem": ("core.actions.bundles", "ActionChangeSetItem"),
    "ChangeSet": ("core.actions.bundles", "ChangeSet"),
    "ChangeSetItem": ("core.actions.bundles", "ChangeSetItem"),
    "ACTION_BUNDLE_SCHEMA": ("core.actions.bundles", "ACTION_BUNDLE_SCHEMA"),
    "ACTION_BUNDLE_SCHEMA_VERSION": ("core.actions.bundles", "ACTION_BUNDLE_SCHEMA_VERSION"),
    "ACTION_CHANGE_SET_SCHEMA": ("core.actions.bundles", "ACTION_CHANGE_SET_SCHEMA"),
    "ACTION_CHANGE_SET_SCHEMA_VERSION": ("core.actions.bundles", "ACTION_CHANGE_SET_SCHEMA_VERSION"),
    "BUNDLE_SCHEMA": ("core.actions.bundles", "BUNDLE_SCHEMA"),
    "BUNDLE_SCHEMA_VERSION": ("core.actions.bundles", "BUNDLE_SCHEMA_VERSION"),
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
