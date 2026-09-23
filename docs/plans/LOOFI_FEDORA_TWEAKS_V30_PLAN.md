# Loofi Fedora Tweaks v30.0.1 "Steady" — Stability and Measured Performance

Status: local release candidate; publication and installation are not
authorized by this plan.

## Goal

Improve the stability and measurable startup cost of the existing v29.0.1
Utility application without adding user-facing features. Keep Action Center as
the sole authority for persistent system changes and preserve existing CLI,
JSON, action ID, saved-state, and route contracts.

The historical `v30.0.0` tag is a separate, immutable lineage and remains
untouched. v30.0.1 is the unique candidate identity for this work.

## Baseline

- Public product baseline: v29.0.1 Utility.
- Initial before-change diagnostic: ten clean offscreen starts after two
  warmups; median meaningful Home time 257.693 ms and median resident memory
  80,840 KiB. Subsequent single-order runs showed substantial host-load drift,
  so the accepted before/after comparison alternates revisions and is recorded
  in `docs/reports/V30.0.1_PERFORMANCE.md`.
- Saved coverage snapshot: 85% repository-wide, 0% for the operation controller,
  and 47% for the Qt adapter.
- The startup benchmark and all measurements use temporary state and an
  offscreen Qt platform. They do not establish physical desktop qualification.

## Work

1. Secure operation preparation, confirmation, execution, and verification.
   Preserve a truthful terminal result when cancellation or close arrives after
   execution starts. Keep shutdown pending until the worker ends and its result
   has been recorded. Reject overlapping changes and release worker and Qt
   objects after each run.
2. Add regression tests for per-item Install outcomes, Tune stop-on-error,
   independent Update sources, timeout and missing-tool failures, malformed
   results, stale source data, reboot follow-up, and resumed verification.
3. Defer Install, Tune, Fix, and Update construction through the existing
   `LazyWidget` mechanism. Keep direct routes and reuse each page instance.
4. Synchronize v30.0.1 metadata, roadmap, race lock, architecture, changelog,
   package metadata, and release-candidate notes.

## Acceptance

- Operation controller and Qt adapter each reach at least 85% direct line
  coverage; total repository line coverage remains at least 85%.
- Real controller and Qt tests cover interruption during work, close/quit
  deferral, saved result consistency, reboot continuation, partial results,
  failure handling, and non-overlapping execution.
- Thirty worker cycles and thirty utility-page enter/leave cycles complete
  without retained worker threads or growing window-owned Qt object counts.
- Ten comparable after-change starts improve median startup time or RSS by at
  least 10%, while the other metric does not regress by more than 15%.
- Focused tests, `LOOFI_IPC_MODE=disabled QT_QPA_PLATFORM=offscreen just verify`,
  `just stats-check`, architecture and release checks, packaging validation,
  and RPM smoke checks pass.
- Physical KDE/GNOME, Polkit, Atomic, reboot, keyboard, and Orca checks remain
  explicitly `unverified` unless performed on the named environments.

## Scope boundary

The result is a locally verified release candidate. Do not install it on the
host, publish artifacts, create a tag, or change host settings as part of this
plan.
