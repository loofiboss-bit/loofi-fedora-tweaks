# v19 Phase 1 Canonical System Check Domain

## Outcome

Phase 1 adds one PyQt-free definition of a System Check without changing the
GUI, routes, startup path, execution boundary, or product version.

The closed `system-check-quick-v1` profile composes five existing read-only
collector surfaces:

1. State Doctor integrity findings;
2. the bounded Daily Maintenance subset for updates, failed services, root
   storage, package health, and recovery protection;
3. reclaim analysis;
4. non-migrating Action Center plan/run inspection;
5. pending Atomic deployment state.

Each source has an explicit timeout and duration. A source failure yields a
partial result when other sources complete; complete source failure yields a
failed result. Cancellation cancels pending work and persists nothing. Running
timeout work has no mutation authority and cannot later append a result.

## Finding and mapping contract

`FindingEvidence`, `SystemFinding`, `CheckSourceError`, and
`SystemCheckResult` are frozen contracts. Evidence is redacted before it is
frozen. Fingerprints are SHA-256 digests over normalized redacted facts,
finding ID, and explicit Traditional/Atomic applicability; presentation text
and timestamps do not change identity.

Each finding carries an explicit freshness state. Manual guidance carries a
machine-readable reason code, and only completed, partial, cancelled, and
failed states may be persisted as terminal results; queued and running remain
transient progress states.

Findings reject executable keys and callbacks. Critical findings require either
an audited action ID or manual guidance. Static mappings currently permit only:

- `failed-service` to `restart-failed-service`, deriving the exact `service`
  parameter from closed evidence;
- `reclaimable-package-cache` to `dnf-clean-all` on Traditional Fedora with no
  open parameters.

The gate rejects unknown or manual-only actions, parameter-schema drift,
variant broadening, missing evidence, invalid parameter values, and
materialized actions that do not match the static mapping.

## State and migration decision

The v18 `HealthTimelineStore` remains the structured history authority and the
SQLite metric timeline remains supporting evidence. Completed and partial
results are nested under
`HealthSnapshot.daily_maintenance.system_check`; the health snapshot envelope
stays at schema 1. Existing v18 snapshots without that nested member remain
readable, and unknown-future health schemas retain their read-only behavior.

System Check uses `ActionPlanStore.list_read_only()` and
`ActionRunStore.list_read_only()`. These methods parse supported v1-v3 data
without triggering the existing writable migration path.

Action Center schema v3 has no extension-safe metadata field, and its plan
digest protects executable facts. Finding context therefore cannot be added
safely in Phase 1. Phase 4 must introduce one reviewed v3-to-v4 migration before
persisting finding context. No Action Center schema or digest changed here.

## Compatibility

- No route, alias, saved navigation value, favorite, setting, or GUI class
  changed.
- No cold-start probe, timer, QThread, or realized page provider was added.
- Traditional and Atomic applicability is explicit on every finding.
- Action Center remains the exclusive owner of preflight, command rendering,
  privilege, confirmation, execution, and verification.
- No product version, package metadata, tag, or remote state changed.

## Verification

The Phase 1 gate passed:

```text
just test-file test_system_check_models     8 passed
just test-file test_system_check_service    8 passed
just test-file test_system_check_mappings   5 passed
just test-file test_observability           2 passed
just test-file test_state_v14               21 passed, 5 subtests passed
just lint                                   passed
just typecheck                              passed
```

Affected compatibility coverage also passed for Daily Maintenance, health
snapshot/timeline/redaction, and the v14 Action Center lifecycle and stores.
The version-neutral product-contract and architecture validators passed.

## Deferred

- Phase 2 owns the explicit asynchronous Home trigger and UI cancellation
  wiring. The service is not called during cold startup.
- Phase 3 owns the canonical page and route adapters.
- Phase 4 owns finding-context schema v4 and Action Center handoff.
- Phase 5 owns before/after resolution comparison and exported support
  evidence.
- Physical Fedora Traditional/Atomic certification and release gates remain
  Phase 6 work.

Proposed commit message:

```text
feat(core): add canonical read-only system check domain
```
