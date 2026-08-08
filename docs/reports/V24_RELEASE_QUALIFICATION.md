# V24 Local Release Qualification

## Result

v24.0.0 "Flow" is a locally qualified release candidate. The repository
implementation, focused regressions, full deterministic suite, 86% coverage
floor, lint, mypy, architecture, packaging, documentation, and adapter-drift
gates pass in the current checkout.

This section records the local qualification snapshot. Publication was
subsequently authorized as a separate exact-tag workflow with independent
public readback; the local results below do not stand in for that evidence.

## Authority and baseline

- Baseline branch: `master`
- Baseline commit: `b1c92bf100a365d6ff1652cd0f47a044f809ae51`
- Baseline full gate: 7,048 passed, 61 skipped, 1,217 subtests, 86.36% coverage
- Product metadata: v24.0.0 "Flow"
- Architecture: `.workflow/specs/arch-v24.0.0.md`
- Tasks: `.workflow/specs/tasks-v24.0.0.md`

## Requirement evidence

| Requirement | Local evidence |
| --- | --- |
| REQ-001 | Six stable destinations, route identity, semantic sidebar state, mnemonic-safe labels, deterministic scale contracts |
| REQ-002 | Shared headers, sections, action roles, state/feedback, search/filter, summary, row, and safety-review components |
| REQ-003 | PyQt-free persisted onboarding, inert Home construction, deterministic next action, navigation-only common tasks |
| REQ-004 | Discover/Loofi distinction, source/status application rows, explicit update lifecycle, separate Traditional/Atomic copy |
| REQ-005 | Problem → Checks → Results, explicit read-only start, service-only collection, retained history and export |
| REQ-006 | Review queue/catalog separation, master-detail safety evidence, one lifecycle action, inert browse/select/preview |
| REQ-007 | Explicit Network, System Information, and Settings feedback; Action Center and Troubleshooting decomposed below 900 lines |
| REQ-008 | Focused tests, complete gates, synchronized metadata/docs, isolated scale captures, and honest physical/public limits |

## Automated qualification

The final command set is executed with `LOOFI_IPC_MODE=disabled` and Qt UI
tests use `QT_QPA_PLATFORM=offscreen` where applicable.

| Command | Result |
| --- | --- |
| `just test` | Passed: 7,076 passed, 61 skipped, 1,237 subtests, 0 failed |
| `just test-coverage` | Passed: 86.47% coverage |
| `just lint` | Passed |
| `just typecheck` | Passed |
| `just check-drift` | Passed |
| `just check-packaging` | Passed |
| `just validate-release` | Passed |
| `just verify` | Passed: lint, mypy, architecture, 7,076 tests, and 86.47% coverage |
| `python3 scripts/bump_version.py --check` | Passed |
| `git diff --check` | Passed |

## Visual and accessibility evidence

The real PyQt application was captured with a deterministic temporary profile
at `QT_SCALE_FACTOR=1.0` and `QT_SCALE_FACTOR=1.4`. Home, Applications,
Troubleshooting, Action Center, and Settings Appearance were inspected at both
scales. The captures showed no visible clipping, overlap, mnemonic artifacts,
or contradictory Action Center lifecycle state.

Automated component and geometry contracts cover 100%, 125%, 140%, 150%, and
200%, including accessible names, non-color-only feedback, focusable actions,
disabled state, and status text. Offscreen screenshots do not prove a physical
Wayland session, real keyboard traversal, focus-ring visibility on a compositor,
or audible screen-reader output.

## Explicitly unverified or separate

- Fresh Fedora Atomic/Kinoite installation and reboot path: **unverified**
- Physical Fedora KDE Wayland interaction: **unverified**
- Manual keyboard-only journey: **unverified**
- Audible Orca journey: **unverified**
- Commit, push, tag, GitHub/CI/CodeQL, assets, attestations, COPR, package
  signatures, clean installation, and public readback are **separate release
  evidence** and are not claimed by this local qualification report.
