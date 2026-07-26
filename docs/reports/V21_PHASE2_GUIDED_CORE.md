# V21 Phase 2 Guided Core Journey

Date: 2026-07-26  
Baseline commit: `841218ef4dbfa6368136bd3d8cbc1c394ec81258`  
Product version: `20.0.0 "Continuity"`  
Active target: `21.0.0 "Resolve"`

## Outcome

Phase 2 connects the existing Home, Applications, System Check, Action Center,
and Trusted Change Journal presentation into a clearer
See → Understand → Review → Apply → Verify journey. It adds no command,
persistence, policy, confirmation, execution, CLI, API, daemon, package,
version, tag, or remote-service change.

## Guided Home

- Immutable, PyQt-free `GuidedTask` values point only at existing route, plan,
  run, reboot, System Check, or activity identifiers.
- Guided tasks cannot carry commands, callbacks, policy, confirmation, or
  execution behavior.
- Home keeps one truthful status summary separate from one primary task so the
  same warning is not repeated as both status and instruction.
- Secondary attention remains bounded at three and common tasks at four.
- At most one additional active-work task is projected from an existing running,
  verifying, or reboot-waiting Action Center run.
- Saved Home composition remains deferred until after the first Home frame.
  Construction starts no collection, subprocess, timer, or worker thread.

## Application review

- Every application row shows explicit source and installation-status badges.
- Search, source, and installed-status filters compose without changing the
  remote/cached catalog contract.
- Available package controls say `Review install` or `Review removal`.
- Each control still emits exactly one closed Action Center review request.
  The Applications page does not execute a package command.
- External repository and vendor-RPM entries remain unavailable or manual-only
  under the existing policy.

## System Check local views

- Overview, Findings, and History now use `LocalViewSwitcher` inside the single
  canonical System Check route.
- The route-level `SectionNavigator` remains owned by the destination shell.
- Stable `health` and `maintenance:health-timeline` routes and deep-link
  preselection remain unchanged.
- Reading the page still loads persisted results only; new collection starts
  explicitly from Home.

## Activity & Recovery states

The PyQt-free `ActivityPresentationState` contract covers:

- initial and loading;
- empty, partial, truncated, and loaded;
- selected, recoverable, and manual-only;
- error with or without a previously loaded snapshot.

The table appears only when events exist. Change details appear only after a
selection. The recovery review control appears only for a selected event with
closed Action Center recovery metadata. Manual guidance never exposes an
executable recovery control.

## Verification

- Focused Phase 2 Home, Applications, System Check, and Activity matrix:
  `53 passed`.
- Full repository suite: `6,847 passed, 61 skipped`.
- Full repository coverage: `86.49%`, above the `86%` gate.
- Full repository lint and mypy: passed.
- Architecture validator: passed.
- Product contract: passed with all 81 routes preserved.
- Stabilization rules, release-document validation, and agent-adapter drift:
  passed.
- Startup benchmark, two warmups and seven measured offscreen runs:
  - meaningful Home median: `163.437 ms` (ceiling `250.094 ms`);
  - RSS median: `75,868 KiB` (ceiling `83,582 KiB`);
  - one realized Home provider;
  - zero subprocess probes, active timers, running QThreads, and System Check
    runtime imports.

Offscreen tests do not certify compositor behavior, AT-SPI output, RTL, or
Wayland/X11 scaling. Those remain explicit Phase 3 and Phase 4 gates.

Product metadata remains v20.0.0. Phase 3 has not started.
