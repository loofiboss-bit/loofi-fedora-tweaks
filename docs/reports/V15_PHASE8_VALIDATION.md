# v15 Phase 8 Validation

Date: 2026-07-18  
Branch: `v15-essentials`  
Base commit: `9e910e597a736a7156e5ac965e25666a7e70db1d`

## Scope and authority

This report closes only Phase 8 of `LOOFI_FEDORA_TWEAKS_V15_PLAN.md`.
`V15_PHASE0_BASELINE.md` supplied the current-repository adaptation and the v14
performance, workflow, state, routing, platform, API, CLI, daemon, and Action
Center baselines. No Phase 9 or Phase 10 work, version change, release, commit,
or remote operation is included.

## Implemented Phase 8 behavior

| Task | Result |
| --- | --- |
| V15-P8-001 | New profiles follow the native Qt/KDE theme and font by default. Explicit dark, light, and high-contrast choices still load packaged QSS. Migration treats an already stored theme as an explicit user choice. |
| V15-P8-002 | Removed the global font family, deleted obsolete Quick Actions selectors, consolidated duplicate legacy-sidebar selectors, and added stable destination, route-card, state, result, and focus selectors. Monospace remains scoped to technical output. |
| V15-P8-003 | All 28 built-in plugin specs and runtime metadata use packaged semantic icon IDs. Ordinary emoji were removed from GUI buttons, titles, and lists in `ui/*.py`; readable text now carries status. |
| V15-P8-004 | `RouteCard` owns a typed activation signal, stable route ID, accessible name/description, visible focus, and Enter/Return/Space/mouse activation. Home navigation cards use this component without changing their routes. |
| V15-P8-005 | Added presentation-only `LoadingState`, `EmptyState`, `UnavailableState`, `ResultBanner`, `ActionProgress`, and `DetailsDisclosure` components. |
| V15-P8-006 | Applied the shared states to applications, updates, slow-system diagnosis, reclaim analysis, backup protection, lazy loading, and Action Center presentation. Existing field aliases were retained where tests or callers rely on them. |
| V15-P8-007 | Offscreen layout checks cover 860x720 minimum width; 1280x720 and 1366x768 at 100%; 1920x1080 at 100% and 125%; and 2560x1440 at 125%, 150%, and 200%. |
| V15-P8-008 | Automated checks cover keyboard route activation, keyboard Details disclosure, focus policy, focus QSS, accessible names/descriptions, textual status, and non-color-only result kinds. |
| V15-P8-009 | Re-ran one warm-up plus ten isolated startup measurements and re-counted the five standard workflows from visible Home or the standard destination surface. |
| V15-P8-010 | Accepted environment and compatibility exceptions are recorded below. |

## Compatibility preserved

- Action Center still uses the v14 catalog, plan, confirmation, optional
  no-rollback acknowledgement, asynchronous run, separate verification,
  persistence, and transition tables. Shared states present its data but do not
  own or replace its state machine.
- State schema, atomic writes, backups, redaction, support exports, route IDs,
  aliases, deep links, favorites, and navigation-mode migrations are unchanged.
- Traditional Fedora continues to use DNF and Atomic Fedora continues to use
  rpm-ostree/manual-only branches where required. No package operation or
  privilege boundary changed.
- CLI, API, daemon, IPC, and externally loaded plugin contracts are unchanged.
  Legacy emoji-to-icon aliases remain in `ui/icon_pack.py`, and the old decorated
  layered-package value is still accepted, while new GUI rows use plain text.
- No version file, spec version, or `pyproject.toml` version changed. The version
  remains `14.0.0` during v15 implementation.

## Startup and resource measurements

Command:

```bash
PYTHONDONTWRITEBYTECODE=1 QT_QPA_PLATFORM=offscreen \
PYTHONPATH=loofi-fedora-tweaks \
python3 scripts/benchmark_startup.py \
  --warmups 1 --runs 10 \
  --output /tmp/loofi-v15-phase8-startup.json
```

| Measurement | v14 Phase 0 | v15 Phase 2 | v15 Phase 8 | Phase 8 vs v14 |
| --- | ---: | ---: | ---: | ---: |
| GUI import median | 149.132 ms | 97.502 ms | 105.684 ms | 29.13% lower |
| MainWindow median | 4544.718 ms | 165.995 ms | 147.445 ms | 96.76% lower |
| Meaningful Home median | 4552.202 ms | 172.452 ms | 151.924 ms | 96.66% lower |
| Meaningful Home range | 4063.653-5181.762 ms | 169.127-178.130 ms | 145.231-154.851 ms | - |
| RSS median | 107446 KiB | 80304 KiB | 76068 KiB | 29.20% lower |
| RSS range | 106768-107812 KiB | 80104-80384 KiB | 76040-76148 KiB | - |
| Imported modules | 527 | 331 | 288 | 45.35% lower |
| Imported `ui` modules | 38 | 8 | 12 | 68.42% lower |
| Imported `ui.*_tab` modules | 30 | 2 | 2 | 93.33% lower |
| Runtime plugin instances | 29 | 1 | 1 | 96.55% lower |
| Live Qt widgets | 2425 | 333 | 356 | 85.32% lower |
| Active timers | 9 | 0 | 0 | eliminated |
| Running QThreads | 2 | 0 | 0 | eliminated |
| Subprocess probes | 54 | 0 | 0 | eliminated |

The four additional top-level UI imports versus Phase 2 are the destination
navigation modules and the Phase 8 shared-state module. Specialist tab imports,
runtime instances, timers, threads, and subprocess probes remain bounded.

## Workflow decision counts

Counts use the Phase 0 method: start on visible Home or the standard destination
surface; count navigation, selection, primary action, and explicit confirmation;
do not count typing or passive progress.

| Workflow | Phase 8 decisions/clicks | Evidence |
| --- | ---: | --- |
| Update the system | 3 | Home route, Update All, explicit confirmation. |
| Install an application | 3 | Home route, per-app Install, explicit confirmation. |
| Diagnose a slow system | 2 | Home performance route opens the Performance subtab, then Analyze Slow System. |
| Free disk space analysis | 3 | Software & Updates destination, Cleanup section, Analyze Reclaimable Space. |
| Protect by creating a recovery point | 3 | Home Backups route, Next, Create Snapshot; tool detection is passive. |
| Restore an existing recovery point | 5-6 | Backups route, wizard navigation, selection, Restore, and explicit confirmation depending on starting page. |
| Action Center lifecycle | 6-7 | Selection, Review & Plan, Run, explicit confirmation, optional no-rollback acknowledgement, and separate Verify remain intact. |

Phase 8 changes presentation only, so these counts do not remove any safety
decision. `scripts/validate_v15_phase6_workflows.py --json` also passed with
five canonical workflows, zero host probes, zero mutations, and the unchanged
three-action v14 catalog.

## Verification

Logical slices were tested immediately after each behavior change. The final
evidence is:

- Phase 8 visual/accessibility contract: 8 passed.
- Theme/settings/main-entry/plugin metadata targeted suites: 67 passed.
- Applications, updates, cleanup, Action Center, slow-system, backup, hardware,
  diagnostics, navigation, and UI smoke suites: all passed in isolated runs.
- Action Center v14 regression group: 84 passed.
- State/observability/support-bundle regression group: 37 passed.
- Navigation/route/favorites/sidebar regression group: 98 passed across isolated
  runs.
- Traditional/Atomic regression group: 81 passed after isolating the maintained
  import-stub test.
- CLI/API/daemon/IPC regression group: 183 passed.
- Release contract tests: 42 passed.
- Final full suite: 7604 passed, 40 skipped, 614 subtests passed.
- Full coverage run immediately before the final packaged Home-icon assertion:
  7603 passed, 40 skipped, 610 subtests passed; coverage 86.08%, above the 85%
  gate. The final production change is one icon-ID literal and the subsequent
  targeted and full-suite reruns are green.
- Flake8: passed using `.venv/bin/flake8` because the executable is not on the
  non-interactive shell PATH.
- `just validate-release`: passed.
- `just check-drift`: passed.
- `just check-packaging`: passed.
- `scripts/check_fedora_review.py`: passed.
- `git diff --check`: passed.

Mypy still reports four pre-existing `no-any-return` findings in
`ui/icon_pack.py`, `utils/command_runner.py`, `ui/confirm_dialog.py`, and
`ui/community_tab.py`. The Phase 8 edits do not touch the reported return
statements; fixing them would be unrelated scope.

## Accepted exceptions and remaining issues

- The responsive matrix uses Qt offscreen rendering and scaled fonts. Actual KDE
  compositor DPI behavior at 125%, 150%, and 200% was not available in this
  session.
- Real Wayland and X11 sessions were not available. Both remain supported by the
  unchanged Qt window and routing contracts, but live rendering requires a
  desktop validation pass.
- Orca/AT-SPI screen-reader announcements were not exercised. Automated tests
  verify accessible names, descriptions, textual status, focus policy, and
  keyboard operation; live announcement timing remains manual validation.
- Automated contrast-ratio sampling was not added. System mode delegates palette
  contrast to Qt/KDE, while the explicit high-contrast QSS retains its existing
  black/white/yellow information hierarchy and visible focus borders.
- Emoji aliases and external plugin metadata remain accepted for compatibility.
  The Phase 8 no-emoji contract is enforced on built-in runtime metadata and
  ordinary GUI source labels, not on CLI output or third-party plugin payloads.
- The existing clipboard-server test still emits its known handled thread
  warning during the full suite; it does not fail the suite and is unrelated to
  Phase 8.

## Files changed

Visual system and settings:

- `loofi-fedora-tweaks/assets/highcontrast.qss`
- `loofi-fedora-tweaks/assets/light.qss`
- `loofi-fedora-tweaks/assets/modern.qss`
- `loofi-fedora-tweaks/main.py`
- `loofi-fedora-tweaks/utils/settings.py`
- `loofi-fedora-tweaks/ui/main_window.py`
- `loofi-fedora-tweaks/ui/settings_tab.py`

Shared components and standard-workflow presentation:

- `loofi-fedora-tweaks/ui/shared_states.py`
- `loofi-fedora-tweaks/ui/layout_primitives.py`
- `loofi-fedora-tweaks/ui/lazy_widget.py`
- `loofi-fedora-tweaks/ui/atlas_dashboard_tab.py`
- `loofi-fedora-tweaks/ui/software_tab.py`
- `loofi-fedora-tweaks/ui/maintenance_tab.py`
- `loofi-fedora-tweaks/ui/monitor_tab.py`
- `loofi-fedora-tweaks/ui/backup_tab.py`

Semantic built-in icon metadata and plain-text GUI labels:

- `loofi-fedora-tweaks/core/plugins/spec.py`
- `loofi-fedora-tweaks/core/home/service.py`
- `loofi-fedora-tweaks/ui/agents_tab.py`
- `loofi-fedora-tweaks/ui/ai_enhanced_tab.py`
- `loofi-fedora-tweaks/ui/automation_tab.py`
- `loofi-fedora-tweaks/ui/base_tab.py`
- `loofi-fedora-tweaks/ui/community_tab.py`
- `loofi-fedora-tweaks/ui/confirm_dialog.py`
- `loofi-fedora-tweaks/ui/desktop_tab.py`
- `loofi-fedora-tweaks/ui/development_tab.py`
- `loofi-fedora-tweaks/ui/diagnostics_tab.py`
- `loofi-fedora-tweaks/ui/extensions_tab.py`
- `loofi-fedora-tweaks/ui/fingerprint_dialog.py`
- `loofi-fedora-tweaks/ui/gaming_tab.py`
- `loofi-fedora-tweaks/ui/hardware_tab.py`
- `loofi-fedora-tweaks/ui/health_detail_dialog.py`
- `loofi-fedora-tweaks/ui/health_timeline_tab.py`
- `loofi-fedora-tweaks/ui/logs_tab.py`
- `loofi-fedora-tweaks/ui/mesh_tab.py`
- `loofi-fedora-tweaks/ui/network_tab.py`
- `loofi-fedora-tweaks/ui/notification_toast.py`
- `loofi-fedora-tweaks/ui/performance_tab.py`
- `loofi-fedora-tweaks/ui/permission_consent_dialog.py`
- `loofi-fedora-tweaks/ui/profiles_tab.py`
- `loofi-fedora-tweaks/ui/security_tab.py`
- `loofi-fedora-tweaks/ui/snapshot_tab.py`
- `loofi-fedora-tweaks/ui/storage_tab.py`
- `loofi-fedora-tweaks/ui/system_info_tab.py`
- `loofi-fedora-tweaks/ui/task_wizard.py`
- `loofi-fedora-tweaks/ui/teleport_tab.py`
- `loofi-fedora-tweaks/ui/tour_overlay.py`
- `loofi-fedora-tweaks/ui/virtualization_tab.py`

Packaging and tests:

- `scripts/check_packaging_manifest.py`
- `tests/test_backup_tab.py`
- `tests/test_diagnostics_tab.py`
- `tests/test_hardware_tab.py`
- `tests/test_main_entry.py`
- `tests/test_main_window.py`
- `tests/test_maintenance_tab.py`
- `tests/test_maintenance_updates_regression.py`
- `tests/test_monitor_tab.py`
- `tests/test_plugin_specs.py`
- `tests/test_settings.py`
- `tests/test_settings_extended_v29.py`
- `tests/test_settings_tab_ux.py`
- `tests/test_software_tab.py`
- `tests/test_v15_phase8_visual_system.py`
- `tests/test_v29_features.py`
- `docs/reports/V15_PHASE8_VALIDATION.md`

## Deferred work

- Phase 9 packaging/component go/no-go and any physical package split.
- Phase 10 release documentation, version synchronization, screenshots, release
  artifacts, publication, and release automation.
- The four unrelated pre-existing mypy findings.
- Live Wayland/X11, compositor-scale, Orca/AT-SPI, and instrumented contrast
  validation on a desktop session.
