# Tasks — v30.0.1 "Steady"

Status: implementation and local qualification complete; candidate only.

- [x] CORE-001 | Files: `core/actions/operation_controller.py` | Preserve
  saved run truth after execution and verification errors, including timeouts
  and lost acknowledgements. Tests cover timeout, malformed result, verifier
  exception, and state-store failure.
- [x] QT-001 | Files: `ui/operation_worker.py`,
  `ui/main_window_interactions.py`, `ui/main_window_utility.py` | Defer close
  and quit until the worker has ended and its terminal result is delivered;
  reject overlap and release thread/adapter objects. Add real Qt lifecycle and
  30-cycle tests.
- [x] FLOW-001 | Files: `core/actions/operation_controller.py`,
  `tests/test_operation_controller_v30.py` | Prove Install per-item results,
  Tune stop-on-error, timeouts, missing tools, malformed responses, and reboot
  verification resumption.
- [x] UPDATE-001 | Files: `core/tasks/update_flow.py`,
  `ui/update_workflow.py`, `tests/test_v29_vertical_flows.py` | Represent
  cancellation as stale source data while preserving independent source state.
- [x] UI-001 | Files: `ui/main_window_utility.py`,
  `tests/test_v29_shell.py` | Lazily create the four workflow pages on first
  visit, preserve direct links, reuse instances, and exercise thirty
  enter/leave cycles.
- [x] DOC-001 | Files: roadmap, plan, architecture, changelog, release notes,
  package metadata, race lock | Synchronize the local v30.0.1 candidate and
  preserve the historical `v30.0.0` tag.
- [x] QUAL-001 | Files: qualification report | Pass direct controller and Qt
  coverage >=85%, total coverage >=85%, all deterministic verification,
  documentation and architecture checks, package checks, and RPM smoke tests.
- [x] PERF-001 | Files: `docs/reports/V30.0.1_PERFORMANCE.md` | Record ten
  comparable after-change runs and the thirty-cycle object/thread result. Meet
  the stated 10% improvement and 15% maximum-regression thresholds.

## Physical and external gates

KDE/GNOME desktop, Polkit, Atomic, reboot, keyboard, and Orca checks remain
`unverified` unless actually performed. Installation, publication, tag
creation, and remote release workflows are outside scope.
