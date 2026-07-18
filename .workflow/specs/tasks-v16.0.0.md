# Tasks — v16.0.0 "Clarity"

## Phase 0 — Baseline and scope lock

- [x] P0-01: anchor product comparison at the published v15.0.0 tag and confirm
  that Phase 0 changes no product behavior or version metadata.
- [x] P0-02: make the reconciled v16 plan the sole active scope authority and
  reduce the root roadmap to current release state plus linked history.
- [x] P0-03: inventory routes, aliases, redirects, lazy ownership, schemas,
  navigation debt, styling debt, screenshots, and startup/resource evidence in
  reproducible machine-readable and human-readable artifacts.
- [x] P0-04: preserve supplied screenshots and capture the real v15 MainWindow
  matrix with hashes, reproduction commands, and clearly labelled offscreen
  font-scaling limitations.
- [x] P0-05: activate matching v16 workflow contracts and verify that the v15
  release remains complete while v16 is the single newer active target.

## Implementation phases

- [x] P1: introduce the structural theme engine and semantic design tokens.
- [x] P2: implement and test the shared component library and page scaffold.
- [x] P3: redesign the application shell and responsive section navigation
  while preserving all routes, aliases, migrations, and lazy loading.
- [x] P4: redesign Home and System, moving the existing Export Report action
  without adding new System Information behavior.
- [ ] P5: redesign Software & Updates, Network & Security, Desktop, and Settings.
- [ ] P6: adopt shared components in Advanced and remove superseded legacy UI
  and styling only after compatibility coverage exists.
- [ ] P7: complete real-shell responsive, theme, keyboard, accessibility,
  contrast, Wayland/X11, and compositor-scaling validation.
- [ ] P8: run full regression, startup/resource, Traditional/Atomic, packaging,
  release-evidence, and security gates; then bump to v16 only when every gate
  passes.

## Completion contract

Unchecked v16 tasks represent later development phases and must not affect
`--require-completed-tasks` or `--require-publish-ready-tasks` while the code
version remains the completed v15.0.0 release. Those flags continue to validate
`tasks-v15.0.0.md` until the deliberate Phase 8 version bump.
