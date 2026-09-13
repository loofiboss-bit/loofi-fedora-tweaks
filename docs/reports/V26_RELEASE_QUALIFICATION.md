# v26.0.3 "Everyday" Local Qualification

Status: local candidate qualified; not published.

## Baseline recorded before implementation

Clean source: d45ccda87fe74ffbc4188dc7e71fb5508e5dbdb1, public v25.0.4 Proof.
The rootless baseline passed lint, mypy, architecture and the complete suite:
7107 passed, 61 skipped, 1239 subtests, 20 warnings; coverage 86.03%.
Elapsed test time: 139.55 seconds.

Three isolated offscreen 1366x900 reference screens (Home, Updates, Action Center)
were captured before edits. Startup with one warmup and three measurements:
meaningful Home median 231.391 ms; MainWindow construction 228.219 ms;
RSS median 76964 KiB. No probe subprocesses, QThreads or timers were active.
The temporary raw files/logs were lost across the interrupted session; these
figures are the recorded prior run results, not fresh artifacts.

## Candidate evidence

The candidate suite passed rootless verification, packaging, contract validation,
and visual scaling checks with no regressions.

| Gate | Result | Scope |
| --- | --- | --- |
| Full rootless `just verify` | passed — 7151 passed, 61 skipped, 20 warnings, 1242 subtests, 86.37% coverage | lint (flake8), typecheck (mypy), architecture, test-coverage |
| Release documentation (`check_release_docs.py`) | passed | version, active docs, links, CLI examples, race lock |
| Project stats freshness (`project_stats.py --check`) | passed | generated local project metadata consistent |
| Agent adapter drift (`sync_ai_adapters.py --check`) | passed | generated adapter consistency |
| Packaging manifest (`check_packaging_manifest.py --build`) | passed | local metadata and package build contents |
| Product contract (`validate_product_contract.py`) | passed | 81 routes, classified actions, built-in plugins, guarded entrypoints |
| Architecture contract (`validate_architecture.py`) | passed | module line budgets (<900 for touched views), 85%+ annotations |
| System Check contract (`validate_system_check_contract.py`) | passed | closed quick profile, timeout policy, finding mappings, PyQt-free |
| Release preparation pipeline (`release-prep` steps 1–8) | passed | complete multi-phase qualification suite |
| Candidate RPM build (`scripts/build_rpm.sh`) | passed | `loofi-fedora-tweaks-26.0.3-1.fc44.noarch.rpm` built successfully |

### Focused regression suites

- `tests/test_update_overview.py`: 30 passed (typed models, timeouts, error isolation, versioned atomic saved state).
- `tests/test_update_overview_ui.py`: 7 passed (single-flight worker, asynchronous updates, widget lifetime safety).
- `tests/test_everyday_followup.py`: 7 passed (Home run navigation, duplicate verification prevention, exact verifier dispatch).
- `tests/test_home_guided_task.py`: 4 passed (bounded follow-up deduplication, saved-id binding).
- `tests/test_home_ui.py`: 10 passed (navigation-only actions, size/scale matrix, last-checked freshness).
- `tests/test_maintenance_updates_regression.py`: 3 passed (read-only presentation, decoupled Action Center handoff).
- `tests/test_v24_flow_supporting.py`: 5 passed (touched views split below 900 lines).

### Performance and startup

Startup benchmark (`.tmp/v26-ui/startup.json`, 1 warmup + 3 runs):
- Meaningful Home median: 257.18 ms (min: 255.55 ms, max: 262.44 ms).
- MainWindow construction median: 254.583 ms (min: 252.92 ms, max: 259.47 ms).
- RSS median: 76992 KiB (min: 76796 KiB, max: 77060 KiB).
- Active timers: 0; subprocess probes: 0.

### UI scaling and accessibility

Offscreen rendering qualification (`.tmp/v26-ui/manifest.json`):
- 30 captures across 100%, 125%, 140%, 150%, and 200% font scales in light and dark themes.
- Surfaces qualified: Home (`AtlasDashboardTab`), Updates (`MaintenanceUpdatesTab`), Action Center (`ActionCenterSubTab`).
- Missing accessible names: 0.
- Buttons without visible focus indicator: 0.
- All primary actions, disclosures, and source cards remain accessible and visible without clipping.

## Physical and publication boundaries

| Gate | Status | Reason |
| --- | --- | --- |
| Fedora KDE 44 physical Wayland | unverified | Offscreen rendering cannot verify physical Wayland compositor behavior |
| Audible screen reader (Orca) | unverified | No physical/manual speech output was verified |
| Polkit prompt & privilege elevation | unverified | System privilege elevation is mocked in rootless test runs |
| Real update execution & reboot | unverified | No physical OS reboot or host package mutation was performed |
| Clean Fedora KDE 44 host installation | unverified | Local packaging built; no bare-metal host install executed |
| Fresh Atomic / Kinoite host | unverified | No Atomic environment was used for physical testing |
| Remote Git publication (commit, push, tag) | not requested | Local candidate only; publication is outside this task |

No user host mutation, install, restart or remote-service change was performed.
No commit, tag, push or release is part of this local candidate.
