# V24 Phase 0 Baseline and Scope Lock

Date: 2026-08-08
Baseline commit: `b1c92bf100a365d6ff1652cd0f47a044f809ae51`
Current product and public release: `v23.1.0 "Compass"`
Active local implementation target: `v24.0.0 "Flow"`

## Outcome

The clean V23.1.0 public closure is the exact V24 starting point. V24 is locked
as a local UX-convergence and maintainability release. It adds no route,
standard destination, provider, runtime dependency, background execution, API
or daemon authority, package abstraction, or automatic repair.

## Checkout authority

- Branch: `master`
- HEAD: `b1c92bf100a365d6ff1652cd0f47a044f809ae51`
- Upstream: `origin/master` at the same commit
- Initial worktree: clean; no pre-existing user changes to preserve
- Race lock before V24: v23.1.0 `public-complete`
- Product metadata remains v23.1.0 until the implementation and qualification
  gates pass.

## Baseline verification

Command:

```text
LOOFI_IPC_MODE=disabled QT_QPA_PLATFORM=offscreen just verify
```

Result: PASS.

- 7,109 collected tests
- 7,048 passed, 61 skipped, 0 failed
- 1,217 subtests passed
- 20 warnings
- 86.36% coverage against the 86% gate
- lint, mypy, architecture, stabilization, product-contract, documentation,
  drift, packaging, and project-stat checks passed
- elapsed test/coverage time: 190.46 seconds

No pre-existing failure was observed.

## Visual baseline findings

The five authoritative current screenshots were inspected:

- Home already exposes saved status, a next step, and common tasks, but first
  run guidance is not integrated into the task hierarchy.
- Applications explains the Discover handoff and exposes source/status, but
  uses generic repeated icons and a dense raw row layout.
- Troubleshooting already protects explicit read-only start, but its visual
  hierarchy competes across guidance, local views, cards, and results.
- Action Center exposes lifecycle groups and evidence, but the queue, catalog,
  selection, detail, and Run Plan controls are not a clear desktop
  master-detail workflow.
- Settings uses aligned semantic setting rows in parts of the surface but its
  local feedback vocabulary is incomplete.
- Visible shell/header copy includes mnemonic artifacts such as
  `Software_Updates`; several touched routes repeat generic ellipsis icons.

## Protected starting contracts

- Six standard destinations and every stable route/redirect remain supported.
- Lazy page creation and startup ordering remain unchanged.
- Action Center remains the sole explicit host-mutation authority.
- Page opening, browsing, filtering, selecting, and reviewing remain inert.
- Traditional and Atomic Fedora planning/execution/verification remain
  separate and tested.
- Fresh Atomic, manual keyboard-only, and audible Orca evidence remain
  unverified unless this run obtains genuine physical evidence.

No commit, push, tag, publication, host installation, or external change was
performed during Phase 0.
