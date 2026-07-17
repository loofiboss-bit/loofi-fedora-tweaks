# v15 Phases 0-5 Verification

**Verified:** 2026-07-18

**Scope:** Recovered v15.0.0 "Essentials" phases 0-5

**Version bump:** Not performed

**Release actions:** Not performed

## Git recovery and branch lineage

| Item | Value |
| --- | --- |
| Original branch | `master` |
| v14/base commit | `33f37ec48dea8dee36e69703dd4e71915756e116` |
| Recovery branch | `v15/recovery-phases-0-5` |
| Recovery checkpoint | `2cbcd2c2a6f23b5861c132db1f6efa53ddc9a9ef` |
| Clean integration branch | `v15-essentials` |
| Recovery remote verification | `origin/v15/recovery-phases-0-5` resolved to the checkpoint commit |

The recovery branch was pushed before the working tree was reset to the base
commit for history reconstruction. It was not amended, rebased, force-pushed,
deleted, or otherwise rewritten afterward.

## Reconstructed commits

1. `3105548ce2faa8b5ccb80749c25c739143762eaf` — `docs: add v15 phase 0 baseline`
2. `b40bc72bfacb2fdfc5de1b3da8763d0c8bfa4925` — `refactor: introduce v15 destination and navigation policy`
3. `b6c9ce442dbae7f6a40fa251760482a782fbcf14` — `refactor: defer builtin plugin imports`
4. `94f48a2f56e4e04f0dcdfdf9acc9a81ae1014bff` — `feat: add deferred six-destination discovery shell`
5. `f99add622e2aee6888afb23f30a1c70b685a553b` — `feat: consolidate the v15 home experience`

The recovered implementation couples the real top-level lazy-loader integration,
six-destination host, and unified search inside `ui/main_window.py`. Those parts
were therefore kept together in commit 4 rather than producing knowingly broken
intermediate commits solely to match the preferred example sequence.

## Files and phases represented

The implementation before this report changes 79 files: 6,248 insertions and
3,158 deletions relative to the base commit.

### Phase 0 - baseline and planning evidence

- `docs/reports/V15_PHASE0_BASELINE.md`

### Phase 1 - destinations, policy, visibility, and migrations

- `loofi-fedora-tweaks/core/navigation/areas.py`
- `loofi-fedora-tweaks/core/navigation/destinations.py`
- `loofi-fedora-tweaks/core/navigation/manifest.py`
- `loofi-fedora-tweaks/core/navigation/migrations.py`
- `loofi-fedora-tweaks/core/navigation/models.py`
- `loofi-fedora-tweaks/core/navigation/policy.py`
- `loofi-fedora-tweaks/utils/experience_level.py`
- `loofi-fedora-tweaks/utils/favorites.py`
- `loofi-fedora-tweaks/utils/quick_actions_config.py`
- `loofi-fedora-tweaks/utils/settings.py`
- Directly corresponding navigation, migration, settings, favorites, and
  packaging tests.

### Phase 2 - PluginSpec, lazy loading, and startup deferral

- `loofi-fedora-tweaks/core/plugins/spec.py`
- `loofi-fedora-tweaks/core/plugins/registry.py`
- `loofi-fedora-tweaks/core/plugins/loader.py`
- `loofi-fedora-tweaks/ui/lazy_widget.py`
- Route lifecycle changes in the affected built-in tab modules.
- `scripts/benchmark_startup.py`
- `docs/reports/V15_PHASE2_STARTUP.md`
- Plugin spec, loader, lifecycle, startup, packaging, and compatibility tests.

### Phase 3 - six-destination application shell

- `loofi-fedora-tweaks/ui/navigation/destination_sidebar.py`
- `loofi-fedora-tweaks/ui/navigation/destination_host.py`
- `loofi-fedora-tweaks/ui/main_window.py`
- Destination shell, route history, narrow layout, and integration tests.

### Phase 4 - unified global search and route discovery

- `loofi-fedora-tweaks/core/navigation/search.py`
- `loofi-fedora-tweaks/ui/global_search.py`
- `loofi-fedora-tweaks/ui/command_palette.py` compatibility adapter.
- `loofi-fedora-tweaks/ui/maintenance_tab.py` Action Center preselection only.
- Removed `loofi-fedora-tweaks/ui/quick_actions.py` and its obsolete tests.
- Global search model, UI, keyboard, policy, and non-execution tests.

### Phase 5 - canonical Home

- `loofi-fedora-tweaks/core/home/`
- `loofi-fedora-tweaks/ui/atlas_dashboard_tab.py`
- Removed `loofi-fedora-tweaks/ui/dashboard_tab.py` and its lifecycle tests.
- Home service, UI, smoke, and compatibility tests.

No Action Center core contract, API/daemon contract, version metadata, release
tag, or release workflow state was changed.

## Verification results

### Targeted commit verification

| Slice | Result |
| --- | --- |
| Phase 1 contracts and migrations | 151 passed |
| Phase 2 specs, loaders, lifecycle support, and packaging | 190 passed |
| Community regression in a clean process | 107 passed |
| Phase 2/3/4 shell and search selection | 400 passed; 3 module-cache-sensitive Maintenance tests failed in the combined order |
| Maintenance rerun in a clean process | 139 passed |
| UI tab smoke in a clean process | 60 passed |
| Phase 5 Home and integration selection | 223 passed |

The three transient Maintenance failures were caused by importing the real
module earlier in the same combined process before the test file installed its
module stubs. The file passed 139/139 in isolation, and the canonical full suite
later passed all of those tests in repository order.

### Final commands

| Command | Result |
| --- | --- |
| `git diff --check` | Passed |
| `just lint` | Passed with `flake8 7.3.0` in a temporary verification environment |
| `just typecheck` | Failed with five pre-existing `no-any-return` errors |
| `just test` | Passed: 7,614 passed, 48 skipped, 10 warnings |

`flake8` and `mypy` were initially absent from the host. They were installed in
a temporary environment outside the repository and the checks were rerun.

The mypy failures are:

- `loofi-fedora-tweaks/ui/icon_pack.py:237`
- `loofi-fedora-tweaks/utils/command_runner.py:50`
- `loofi-fedora-tweaks/ui/confirm_dialog.py:255`
- `loofi-fedora-tweaks/ui/community_tab.py:1053`
- `loofi-fedora-tweaks/ui/settings_tab.py:351`

Running the same `mypy 2.3.0` command against base commit `33f37ec` produced the
same five errors (the Community line was 1050 before the v15 lifecycle additions).
The reconstructed v15 implementation therefore adds no new mypy diagnostics,
but the repository-wide typecheck gate remains pre-existingly red.

## Startup and import evidence

The Phase 2 benchmark used ten clean offscreen launches with the same meaningful
Home marker as Phase 0.

| Measurement | v14 Phase 0 | v15 Phase 2 | Change |
| --- | ---: | ---: | ---: |
| Meaningful Home median | 4,552.202 ms | 172.452 ms | 96.21% lower |
| RSS median | 107,446 KiB | 80,304 KiB | 25.26% lower |
| Imported UI modules | 38 | 8 | 78.95% lower |
| Built-in runtime instances | 29 | 1 | 96.55% lower |
| Active timers at Home marker | 9 | 0 | Eliminated |
| Running QThreads at Home marker | 2 | 0 | Eliminated |
| Subprocess probes before Home | 54 | 0 | Eliminated |

All ten runs registered 28 data-only specs and constructed only
`atlas_dashboard` at the marker. The measured 25% Home-render and 15% RSS targets
are exceeded.

## Known risks and remaining work

- Repository-wide typecheck is already red at the base commit and still needs a
  dedicated cleanup goal; no new mypy error was introduced by phases 0-5.
- Optional component detection in the shell currently supplies the logical
  `core` and `specialist` component set. Physical optional-component evidence
  and any RPM split remain the Phase 9 go/no-go.
- `ROADMAP.md`, `ARCHITECTURE.md`, and `.workflow/specs/` still describe v14 and
  have no v15 workflow spec. Updating release authorities remains Phase 10 work.
- The full test suite emitted existing deprecation/resource warnings, including
  one mocked clipboard server thread warning, but no test failed.
- No coverage, package build, CI, COPR, release, or public-readback gate was run;
  those are later release-phase requirements, not phase 0-5 completion claims.

## Phase 6 recommendation

The next Goal should implement Phase 6 as multiple bounded slices, starting with
Action Center placement under Software & Updates while preserving
`maintenance:action-center`, Review/Plan/Run/Verify/History, the three-action
deny-by-default catalog, explicit confirmation, separate verification, expiry,
lease, interruption, CLI/API, and support-bundle contracts. After that, handle
Updates, application install, slow-system diagnosis, disk cleanup, and
protection/recovery as separate independently verified Goals.
