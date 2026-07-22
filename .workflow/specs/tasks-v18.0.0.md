# Tasks — v18.0.0 "Haven"

## Phase 0 — Authority and baseline

- [x] Lock canonical plan, architecture, tasks, race lock, and legacy Sentinel
  archive without changing product version or remote state.
- [x] Record current tests, coverage, startup contract, route inventory,
  architectural hotspots, and mutation surface.
- [ ] Preserve the historical v18 tag as `legacy-v18.0.0-sentinel` immediately
  before an authorized release; do not mutate tags during implementation.

## Implementation

- [x] P1: product catalog, Fedora release policy, operation classification, and static mutation gate.
- [x] P2: Action Center schema v3 and all supported host mutations converged.
- [x] P3: Marketplace retirement, external-code quarantine, Secret Service, and loopback-only API.
- [x] P4: Haven Action Center/Home/Updates/Security/Upgrade/Advanced UX.
- [x] P5: architecture, support-bundle/state, typing, stats, and docs quality.
- [x] P6 local: full regression, performance, security, packaging builds, and artifact smoke tests.

## Release-only gates

- [ ] Run canonical CodeQL and the release workflows from the authorized v18 candidate commit.
- [ ] Physically certify the latest stable Fedora on Traditional KDE/Workstation
  and Atomic Kinoite/Silverblue, including Wayland/X11 and required scaling checks.
- [ ] Bump to v18.0.0 "Haven" only after the physical and canonical CI gates pass.

## Completion

Remote publication, tag changes, version bump, and release evidence remain
blocked until separately authorized after all local gates pass.
