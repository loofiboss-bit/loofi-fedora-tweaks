# Architecture — v19.0.0 "Steward"

## Goal

Compose the existing Home, observability, diagnostics, and Action Center
foundations into one explicit, read-only System Check and verified-resolution
journey.

## Decisions

- `SystemCheckResult` will be a PyQt-free composition of existing trusted
  collectors and stores; v19 must not create a third health database.
- The existing JSON health snapshot store remains the structured finding and
  history source. The existing SQLite metric timeline remains supporting metric
  evidence. Both stores remain readable in place.
- Findings are advisory. They may carry only an existing Action Center action
  ID plus closed parameters, a navigation-only route, or manual guidance.
- Action definitions, fresh preflight, command rendering, policy, confirmation,
  execution, and verification remain exclusively owned by Action Center.
- A System Check is local, privacy-safe, timeout-bounded, cancellable, and
  started explicitly by the user. Home cold startup remains read-only over
  already persisted state.
- `verified` continues to describe an Action Center run. `resolved` requires a
  later System Check comparison; the states are not interchangeable.
- Phase 1 reads v1-v3 Action Center plans and runs without migration or
  rewrite. Phase 4 advances writable plans and runs to schema v4 so optional
  finding context can be persisted without changing the executable definition
  contract. Legacy context-free plans retain their v18 digest calculation.

## Phase 1 domain

- `core/system_check/models.py` owns immutable findings, evidence, source
  errors, and results. Evidence is redacted before freezing and cannot contain
  executable fields or callbacks.
- `core/system_check/service.py` owns the closed
  `system-check-quick-v1` profile. It composes State Doctor, the closed Daily
  Maintenance subset, reclaim analysis, read-only Action Center state, and
  pending Atomic deployment status with per-source timeout and cancellation.
- `core/system_check/mappings.py` is the deny-by-default bridge to existing
  first-party action IDs. Only exact parameters derived from closed evidence
  pass its gate.
- Completed and partial checks are embedded under
  `HealthSnapshot.daily_maintenance.system_check`. The snapshot envelope stays
  at schema 1, so v18 readers and the current atomic/future-schema behavior are
  preserved. Cancelled and wholly failed checks are not stored.
- `core/privacy.py` is the PyQt-free shared redaction authority.
  `core.observability.privacy` remains a compatibility export.

## Phase 2 Home workflow

- Home reads persisted status exactly as before and exposes `Check now` for
  empty, stale, and recoverable-error states. It never starts collection from
  construction, activation, a timer, or a background startup service.
- `core/workers/system_check_worker.py` is the UI adapter for the PyQt-free
  service. It creates the service only after explicit activation, runs it on a
  `QThread`, forwards typed progress, and uses cooperative cancellation.
- Progress names the current closed-profile source, percentage, elapsed time,
  and unavailable sources. User-facing failures are bounded messages without
  tracebacks or raw collector output.
- Completed and partial checks refresh Home only by rereading the persisted
  result. Cancellation and failure leave the previous good snapshot intact.
- Closing Home cancels the worker and, if its bounded shutdown does not finish
  within one second, safely detaches it until its terminal signal.
- Home retains one primary recommendation, at most three attention items, and
  exactly four common tasks. Action Center remains navigation-only from Home.

## Phase 3 canonical presentation

- `ui/system_check_tab.py` is the single Standard-mode System Check
  presentation. Its Overview, Current findings, and History views reuse the
  shared page, navigation, card, status, empty-state, notice, and disclosure
  components.
- `core/system_check/presentation.py` is a read-only, PyQt-free adapter over the
  existing JSON snapshot timeline and SQLite metric timeline. It neither
  collects signals nor creates the metric database, and exposes a stable
  `loofi.system-check` schema-v1 envelope to the CLI.
- `health` remains the canonical overview route.
  `maintenance:health-timeline` remains a stable compatibility route and
  preselects History. Both IDs, their aliases, Home routes, and diagnostics
  routes remain independently resolvable.
- `ui/health_timeline_tab.HealthTimelineTab` remains as an import-compatible
  class name backed by `SystemCheckTab`. Snapshot-history presentation no
  longer lives in `maintenance_action_center.py`, and Standard UI exposes no
  duplicate Record Snapshot action.
- Existing `health snapshot`, `health timeline`, `health-history`, and
  `maintenance today` CLI contracts remain intact. `health check`, `health
  findings`, and `health history` add the canonical System Check commands;
  global `--json` returns only the versioned envelope.
- This phase adds no state schema or migration, deletes no records, and changes
  no Action Center plan, execution, confirmation, or verification behavior.

## Phase 4 finding handoff

- `core/system_check/handoff.py` is the deny-by-default bridge. It accepts only
  a check ID, finding fingerprint, and one of the two System Check origin
  routes, then rereads the newest persisted result and reconstructs the action
  and parameters from closed evidence.
- Only a unique, current, fresh finding with a valid first-party mapping can
  create an Action Center review. Unknown, stale, malformed, variant-mismatched,
  or evidence-tampered findings fail before a plan is written.
- Action plan and run stores use schema v4. Optional `FindingContext` contains
  the check ID, finding fingerprint, independent evidence digest, origin route,
  and affected resources. Writable v1-v3 data migrates atomically with
  last-known-good backup and readback; future schemas remain read-only.
- Finding context is non-authoritative. It is digest-bound when present but is
  excluded from command rendering, parameter policy, preflight, confirmation,
  no-rollback acknowledgement, execution, verification, and lease decisions.
- The System Check page emits identifiers only. Action Center preselects the
  exact mapped action, reruns the handoff validation when Review & Plan is
  activated, regenerates the command from its own definition, and retains the
  existing explicit Run confirmation.
- Manual-only findings display their reason, route, and guidance on System
  Check and expose no Review safe action control.

## Phase 5 verified resolution and support evidence

- `core/system_check/comparison.py` derives schema-v1 before/after outcomes
  without adding a database or rewriting snapshots. Profile, Fedora variant,
  timestamp ordering, and per-source availability determine comparability.
- Every original finding becomes `resolved`, `unchanged`, `worsened`, or
  `not_comparable`. Missing follow-up sources fail closed instead of implying
  resolution; supported legacy results without a source list remain comparable
  only when the follow-up check completed without errors.
- A linked Action Center run exposes verification and finding outcome as
  separate facts. `awaiting_reboot` remains pending; `succeeded` can be paired
  with `resolved` only after a later compatible System Check collected after
  verifier success.
- Action Center offers an explicit Check again handoff only for a successfully
  verified linked run. It routes to Home and starts the existing closed,
  read-only profile after that user activation.
- Home recommends a follow-up check for verified linked work that lacks a later
  comparable result, keeps pending reboot separate, and stops presenting the
  original finding after a later result proves it absent.
- Support Bundle v11 extends v10 with at most two results, bounded findings and
  source errors, one latest comparison, and bounded linked plan/run metadata.
  Existing recursive redaction also covers IPv4, IPv6, and MAC identifiers;
  raw command output remains excluded.
- `GET /api/system-check/latest` is authenticated and loopback-only through the
  existing server. It reads the latest privacy-safe persisted result without
  collection. `health comparison` provides equivalent read-only CLI evidence.
  No API mutation route is added.

## Protected behavior

- Preserve all 80 stable route IDs, aliases, compatibility redirects, saved
  routes, favorites, settings, and direct-link behavior.
- Preserve JSON snapshots, SQLite metrics, Action Center plans/runs/history, and
  unknown-future-schema read-only handling.
- Preserve one action per expiring plan, fresh preflight, explicit confirmation,
  separately requested verification, and no automatic reboot, retry, rollback,
  resume, or broadening of parameters.
- Preserve Fedora Traditional and Atomic policy branches. Fedora 44 remains the
  supported target; Fedora 45 remains preview-only until current certification.
- Preserve the Home startup contract: one realized provider and zero cold-start
  subprocess probes, active timers, or running QThreads.
- Preserve the loopback-only, non-mutating Web API and built-in-only plugin
  execution boundary.

## Phase gates

- Phase 0 changes authority, evidence, and validator naming only; it makes no
  runtime product change.
- Each later phase must pass its plan-specific tests plus the version-neutral
  product-contract and architecture validators before the next phase starts.
- Version metadata changes, tags, and publication are release-only work.
