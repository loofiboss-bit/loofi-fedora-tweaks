# V21 Phase 1 Runtime Lifecycle and Shell

Date: 2026-07-26  
Baseline commit: `841218ef4dbfa6368136bd3d8cbc1c394ec81258`  
Product version: `20.0.0 "Continuity"`  
Active target: `21.0.0 "Resolve"`

## Outcome

Phase 1 establishes one application-owned teardown boundary and separates
route-level shell navigation from local peer-view switching. It does not
change route IDs, persisted data, Action Center policy, CLI/API/daemon
contracts, package metadata, tags, or remote state.

## Runtime lifecycle

- The PyQt-free `ApplicationRuntime` owns uniquely named cleanup callbacks,
  executes them in reverse registration order, shares one bounded deadline,
  records cleanup failures, and is idempotent.
- GUI startup registers EventBus before MainWindow and connects
  `QApplication.aboutToQuit` to the runtime. Reverse teardown therefore stops
  window-owned timers, plugin resources, Pulse, and tray state before EventBus.
- Window cleanup is exact and idempotent for close, tray Quit, and
  `aboutToQuit`. Pulse keeps its existing five-second maximum while honoring
  the remaining runtime deadline.
- EventBus rejects subscriptions and publishes after shutdown, tracks every
  submitted future, cancels pending work, clears subscriptions, and performs a
  bounded executor shutdown. Test reinitialization is explicit.
- AgentScheduler retains each exact `(topic, callback, subscriber_id)` triple
  and uses it for unregister, replacement, and shutdown.

## Shell and navigation

- Destination/header synchronization moved from `MainWindow` into the focused
  `MainWindowShellMixin`; route behavior and lazy plugin ownership are
  unchanged.
- Breadcrumb/header copy resolves presentation metadata and no longer falls
  back to internal route identifiers.
- `LocalViewSwitcher` provides an accessible two-to-five-item local view
  contract with buttons and a compact selector. It exposes no route signal or
  route namespace.
- The compact destination rail explicitly disables horizontal scrolling.
- The seven stale geometry tests now exercise the real flat shell under the
  offscreen platform and close every realized window deterministically.

## Verification

- Focused lifecycle, EventBus, AgentScheduler, component, MainWindow, and
  geometry matrix: `78 passed`.
- Shell import-order regression matrix: `128 passed`.
- Stabilization/runtime matrix: `53 passed`.
- Full repository suite: `6,839 passed, 61 skipped`.
- Full repository lint: passed.
- Full repository mypy check: passed.
- Architecture validator: passed.
- Product contract: passed with all 81 routes preserved.
- Release-document validator and agent-adapter drift check: passed.
- Startup benchmark, two warmups and seven measured offscreen runs:
  - meaningful Home median: `166.218 ms` (ceiling `250.094 ms`);
  - RSS median: `75,980 KiB` (ceiling `83,582 KiB`);
  - one realized plugin;
  - zero subprocess probes, active timers, and running QThreads.

Product metadata remains v20.0.0 and Phase 2 has not started.
