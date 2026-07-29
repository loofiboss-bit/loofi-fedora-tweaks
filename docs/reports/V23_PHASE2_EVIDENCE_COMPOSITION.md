# V23 Phase 2 Evidence Composition

Date: 2026-07-29  
Active target: `v23.0.0 "Compass"`  
Product metadata: `v22.0.0 "Alignment"`  
Scope: local Phase 2 implementation only

## Outcome

Phase 2 composes existing source-owned facts into the inert Compass session
domain without adding collection, UI, execution, or persistence authority.

`core/troubleshooting/` now owns:

- read-only projection adapters for System Check, saved observability,
  Trusted Change Journal, Action Center, and every remaining closed profile
  source through the structured adapter boundary;
- explicit completed, empty, partial, stale, unavailable, timed-out, failed,
  and cancelled source states;
- deterministic composition with exact per-source and per-profile budget
  enforcement;
- deterministic recent-time and exact-resource matching that always produces
  the label **Possibly related**; and
- compatible before/after classification as resolved, unchanged, worsened, or
  not comparable.

No adapter starts a subprocess, launches a worker, writes or migrates source
state, confirms a plan, executes an action, verifies a run, or creates another
database.

## Source ownership

- System Check findings are projected from an existing terminal
  `SystemCheckResult`; the adapter does not rerun the check.
- Observability reads compatible saved health snapshots and trends. The health
  timeline now exposes `load_read_only()`, which supports in-memory decoding of
  older schemas without rewriting the source store.
- Trusted Change Journal events remain source-owned and are reduced to bounded
  change IDs, timestamps, source kinds, and typed resources.
- Action Center plan/run adapters use only caller-supplied records obtained
  through existing read-only store methods. Verification facts do not become a
  resolved troubleshooting result.
- Package, deployment, reboot, application, network, DNS, storage, boot, and
  service evidence enters only through the closed structured source adapter.
  Its source ID, Fedora variant, schema version, timing, facts, and findings
  must match the selected profile.

## Evidence states and budgets

An empty source means the source completed successfully and found no relevant
record. Partial and stale sources may retain bounded facts and findings, but
they always produce a partial session. Unavailable, timed-out, failed, and
cancelled sources retain no facts. Missing applicable sources become explicitly
unavailable.

Every source result must match the exact timeout in the Phase 1 profile
catalog. Composition also rejects a session whose wall-clock boundary exceeds
the profile total budget. A partial or stale source can never produce an
all-clear.

## Conservative correlation

Correlation is pure and deterministic:

- a change may match only if it occurred before the finding;
- `time_proximity` uses the closed seven-day window;
- `shared_resource` requires an exact typed-resource intersection;
- Traditional DNF5 history and Atomic rpm-ostree history are filtered before
  matching;
- future changes and changes without a closed reason are excluded; and
- every retained reference is labelled **Possibly related**, never as a cause.

## Follow-up comparison

Comparison requires distinct, ordered sessions with the same profile version
and Fedora variant. Each original finding is matched by finding type, source,
and typed resources.

- A compatible absent finding is `resolved`.
- A matching finding is `unchanged` unless its severity, closed state rank, or
  a comparable increasing-is-worse numeric fact increased.
- Missing, partial, stale, failed, or schema-incompatible follow-up evidence is
  `not_comparable`.
- Any partial session or not-comparable outcome prevents the overall comparison
  from claiming full comparability.

## Protected contracts

Phase 2 changes no route, destination, GUI, CLI, API, daemon, D-Bus,
support-bundle writer, Action Center schema, product version, package, tag,
installation, or remote state. All 81 routes and the sole Action Center
execution authority remain unchanged.

## Verification

The focused Phase 2 suite covers:

- every explicit evidence state and exact source/total budget rejection;
- System Check, observability, journal, Action Center, and structured adapter
  projections;
- read-only observability decoding without source-store migration;
- Traditional/Atomic change separation;
- deterministic time/resource matching and the fixed label;
- missing, partial, stale, and no-finding session semantics; and
- resolved, unchanged, worsened, source-unavailable, schema-mismatch, and
  variant-mismatch comparisons.

Full repository verification and final project-statistics readback are recorded
in the implementation handoff. Phase 3 remains not started. No physical Fedora,
Wayland, Orca/AT-SPI, Atomic, artifact, installation, signing, CI, COPR, GitHub,
or public-release claim is made by this local phase.
