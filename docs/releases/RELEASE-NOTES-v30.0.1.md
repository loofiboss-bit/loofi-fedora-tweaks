# Release Notes — v30.0.1 "Steady" Local Candidate

**Candidate prepared:** 2026-09-23<br>
**Codename:** Steady<br>
**Status:** Not published; host installation is out of scope.

## Summary

Steady improves the reliability of the existing v29.0.1 Utility workflows. It
keeps completed system changes visible in their saved Action Center state,
reduces first-start work by loading the four task pages only when opened, and
proves the affected flows with direct regression and lifecycle tests.

## Changes

- A late close or cancellation request no longer suppresses an operation result
  after execution has started. Shutdown waits for the worker and delivered
  result; overlapping operations are rejected.
- Timeout, malformed execution results, verifier exceptions, and lost save
  acknowledgements are represented consistently with the saved run state.
- Install retains a result for each application. Tune stops at the first
  failed step. Update cancellation marks only its source stale.
- Install, Tune, Fix, and Update are loaded once on first visit and then reused.
- Existing CLI commands, JSON contracts, action IDs, routes, and persisted
  state schemas are preserved. No user-facing features are added.

## Qualification status

The local gates passed: 4,917 tests passed, 40 were skipped, repository
coverage reached 86.14%, direct controller and Qt adapter coverage reached
92% and 90%, the RPM built and passed isolated launcher and CLI smoke tests,
and startup time improved 52.01% by median. Full results are in
`docs/reports/V30.0.1_QUALIFICATION.md` and
`docs/reports/V30.0.1_PERFORMANCE.md`.

Physical KDE/GNOME, Polkit, Atomic, reboot, keyboard, and Orca checks remain
`unverified` unless they are performed on the corresponding environments.
Offscreen tests do not establish physical qualification.

## Upgrade notes

No user-facing feature or persisted-state migration is planned. The candidate
is not published and must not be installed as part of this work.
