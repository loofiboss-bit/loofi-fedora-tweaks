"""Static, deny-by-default finding mappings into the v18 Action Center."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from core.actions.catalog import ActionCatalog, validate_parameters
from core.system_check.models import SystemFinding


@dataclass(frozen=True)
class FindingActionMapping:
    finding_id: str
    action_id: str
    parameter_sources: tuple[tuple[str, str], ...]
    applicable_variants: frozenset[str]


FINDING_ACTION_MAPPINGS = (
    FindingActionMapping(
        finding_id="failed-service",
        action_id="restart-failed-service",
        parameter_sources=(("service", "service"),),
        applicable_variants=frozenset({"traditional", "atomic"}),
    ),
    FindingActionMapping(
        finding_id="reclaimable-package-cache",
        action_id="dnf-clean-all",
        parameter_sources=(),
        applicable_variants=frozenset({"traditional"}),
    ),
)


def validate_mappings(
    catalog: ActionCatalog | None = None,
    mappings: tuple[FindingActionMapping, ...] = FINDING_ACTION_MAPPINGS,
) -> None:
    """Fail closed when mappings exceed catalog or evidence authority."""
    selected_catalog = catalog or ActionCatalog()
    seen: set[str] = set()
    for mapping in mappings:
        if mapping.finding_id in seen:
            raise ValueError(f"Duplicate finding mapping: {mapping.finding_id}")
        seen.add(mapping.finding_id)
        definition = selected_catalog.get(mapping.action_id)
        if definition is None or definition.operation_class == "manual_only":
            raise ValueError(f"Finding maps to unknown or retired action: {mapping.action_id}")
        parameters = {name for name, _source in mapping.parameter_sources}
        if parameters != set(definition.parameter_schema):
            raise ValueError(f"Finding mapping parameters do not match action schema: {mapping.finding_id}")
        if not mapping.applicable_variants or not mapping.applicable_variants.issubset(definition.supported_variants):
            raise ValueError(f"Finding mapping exceeds action variants: {mapping.finding_id}")
        if any(not source for _name, source in mapping.parameter_sources):
            raise ValueError(f"Finding mapping has an open evidence source: {mapping.finding_id}")


def mapped_action(
    finding_id: str,
    evidence: Mapping[str, Any],
    *,
    atomic: bool,
    catalog: ActionCatalog | None = None,
) -> tuple[str, dict[str, Any]]:
    """Resolve only parameters named by a closed static mapping."""
    selected_catalog = catalog or ActionCatalog()
    mapping = next((item for item in FINDING_ACTION_MAPPINGS if item.finding_id == finding_id), None)
    variant = "atomic" if atomic else "traditional"
    if mapping is None or variant not in mapping.applicable_variants:
        return "", {}
    definition = selected_catalog.get(mapping.action_id)
    if definition is None or definition.operation_class == "manual_only":
        return "", {}
    parameters = {
        parameter: evidence[source]
        for parameter, source in mapping.parameter_sources
        if source in evidence
    }
    if len(parameters) != len(mapping.parameter_sources):
        return "", {}
    decision = validate_parameters(definition, parameters)
    if not decision.allowed:
        return "", {}
    return mapping.action_id, parameters


def validate_finding(finding: SystemFinding, catalog: ActionCatalog | None = None) -> None:
    """Verify a materialized finding against the static mapping gate."""
    if not finding.action_id:
        if finding.severity == "critical" and not finding.manual_guidance:
            raise ValueError("Critical finding has neither action nor manual guidance.")
        return
    action_id, parameters = mapped_action(
        finding.finding_id,
        finding.evidence.facts_dict(),
        atomic="atomic" in finding.applicable_variants and "traditional" not in finding.applicable_variants,
        catalog=catalog,
    )
    if action_id != finding.action_id or parameters != finding.parameters_dict():
        raise ValueError(f"Finding action is not derivable from closed evidence: {finding.finding_id}")
