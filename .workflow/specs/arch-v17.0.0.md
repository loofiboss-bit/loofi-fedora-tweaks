# Architecture — v17.0.0 "Assurance"

## Goal

Converge the five canonical workflows on the existing Action Center lifecycle
without broadening remote or Advanced execution authority.

## Decisions

- Existing catalog IDs remain stable; eight bounded first-party definitions are
  added for updates, applications, cleanup, and recovery-point creation.
- `ActionRun` schema v2 adds plan-aware verification and `awaiting_reboot`.
  Schema v1 remains readable; future schemas remain read-only.
- Preflight facts are included in the plan digest and supplied to verification.
- The Web API is inspection-only: token issuance is the only non-GET route.
- UI and legacy CLI create plans; only Action Center apply executes them.
- Physical specialist packaging remains a NO-GO for v17.

## Protected behavior

- No persisted command is authoritative; apply regenerates the vector and runs
  fresh policy/preflight checks.
- No exit code alone produces `succeeded`.
- No automatic reboot, rollback, retry, or interrupted-run resume.
- One cross-process mutation lease remains mandatory.
- Stable routes, state, startup, Traditional/Atomic policy, and external read
  contracts remain compatible.
