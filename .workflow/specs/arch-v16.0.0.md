# Architecture — v16.0.0 "Clarity"

## Goal

Redesign and consolidate the PyQt6 presentation layer into a clear, responsive,
Fedora-native control center without changing trusted system behavior or public
contracts.

## Frozen compatibility boundaries

- Preserve every v15 route ID, alias, redirect, destination assignment, saved
  navigation value, and lazy-loading boundary.
- Preserve startup budgets and the zero-startup-probe, timer, worker, and
  eager-plugin-instance contracts.
- Preserve Action Center catalog IDs, Review/Plan/Run/Verify/History behavior,
  schemas, leases, expiry, confirmation, rollback, audit, and verification
  semantics.
- Preserve state schemas and migrations plus CLI, JSON, API, daemon, D-Bus, and
  IPC compatibility.
- Preserve Traditional and Atomic Fedora capability behavior, list-based
  commands, timeouts, package-manager detection, and the `pkexec` boundary.
- Keep logical component isolation and lazy loading. v16 does not introduce a
  physical extras RPM.

## Presentation decisions

- The shell owns the page title, description, responsive section navigation,
  content width, and optional header-action placement. Pages provide content
  and declared metadata without duplicating shell hierarchy.
- Replace the application-level horizontal section tab bar with a responsive
  section navigator. Internal tabs remain only where they represent content,
  not application navigation.
- Add explicit data-only section metadata to navigation policy. Never derive a
  destination's section label from whichever route happens to appear first.
- Structural component styling is always present. System-theme mode derives
  semantic colors from `QPalette` instead of clearing component structure.
- Shared tokens and components own spacing, surfaces, actions, states, forms,
  output areas, and empty/loading/error presentation. Broad global QSS rules
  and page-specific inline styles are retired incrementally.
- Standard destinations are completed before Advanced cleanup. Existing
  System Information Export Report becomes a header action; v16 does not add
  Refresh or Copy Summary behavior.

## Delivery boundaries

- Each phase is a small, independently verified commit with focused tests and
  the phase gate recorded in its report.
- Phase 0 is documentation, evidence, and validation-contract work only. It
  must leave product code and `15.0.0 "Essentials"` metadata unchanged.
- Real Wayland/X11 compositor scaling, accessibility technology, contrast, and
  keyboard validation are Phase 7 release evidence. Offscreen scaling captures
  before then are explicitly a proxy.
- Phase 8 owns the version bump, complete regression/performance/packaging
  gates, release evidence, and publication readiness. Remote changes require
  separate explicit authorization.

## Release gates

- The historical meaningful-Home median is 151.924 ms; the relative v16 limit
  is 182.309 ms and the independent absolute limit is 225 ms.
- The six Standard destinations must remain reachable by stable routes with
  lazy construction and no startup work regression.
- No P0/P1 Standard-mode visual defects may remain at the release gate.
- Full local verification, coverage, release-doc, adapter drift, packaging,
  Fedora review, security, artifact, and manual Fedora KDE evidence must pass
  before publication.
