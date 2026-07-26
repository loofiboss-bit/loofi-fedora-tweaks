# V21 Phase 0 Baseline and Scope Lock

Date: 2026-07-26  
Baseline commit: `841218ef4dbfa6368136bd3d8cbc1c394ec81258`  
Exact product tag: `v20.0.0`  
Active target: `v21.0.0 "Resolve"`

## Authority and release state

- `master` matches `origin/master` at the baseline commit.
- The existing changes in `.github/workflows/auto-release.yml` and
  `.github/workflows/ci.yml` predate Resolve and remain outside V21 ownership.
- GitHub v20.0.0 exists at the baseline commit with release assets. COPR build
  `10773551` is terminal `failed`: the RPM build and artifacts succeeded, but
  Pulp `signed_add_and_remove` failed with `PLP0022`. A clean Fedora 44
  repository query exposes only `1:19.0.0-1.fc44`.
- The original requirement to close V20 before V21 was explicitly overridden
  by the user for Phase 0. V20 is therefore recorded as publication-blocked,
  not completed.
- Remote `v21.0.0` points to
  `7328d87b078e3d3361523876eedfa545cbbe2a0d`; remote `v21.0.1` points to
  `c832cce78a47f04a2b512551557219db8dd14e8d`. Phase 0 archives the old release
  notes but does not create, delete, move, or push tags.

## Repository baseline

- 1,393 tracked files, 397 production Python files, 305 test files, and 101
  utility modules.
- The product-contract validator reports 81 stable routes, classified actions,
  built-in-only plugins, and guarded entry points.
- The architecture validator passes catalog authority, System Check,
  module/function budgets, CLI main, and the annotation gate.
- The five largest Python files by bytes are:
  - `core/product_catalog_records.py` — 76,275
  - `core/actions/assurance.py` — 54,015
  - `ui/main_window.py` — 48,032
  - `core/diagnostics/release_readiness.py` — 42,486
  - `cli/main.py` — 40,594
- V21 deliberately limits decomposition to runtime/shell ownership. Product
  catalog, Action Center assurance, diagnostics, and CLI are not broad-refactor
  targets.

## Runtime and performance baseline

The committed [startup evidence](V21_PHASE0_STARTUP.json) uses a temporary
clean profile, Qt offscreen, two warmups, and seven measured runs:

- meaningful Home median: 227.358 ms;
- `MainWindow` median: 224.286 ms;
- RSS median: 75,984 KiB;
- one realized Home provider;
- zero subprocess probes, active timers, and running QThreads.

The committed [System Check evidence](V21_PHASE0_SYSTEM_CHECK.json) records:

- total median: 309.881 ms against a 3,500 ms budget;
- state-integrity: 95.503 ms;
- maintenance: 308.234 ms;
- storage-reclaim: 32.202 ms;
- action-center: 27.665 ms;
- pending-reboot: 4.647 ms;
- no collection errors.

The V21 performance ceiling is 250.094 ms for meaningful Home and 83,582 KiB
RSS, both calculated as Phase 0 × 1.10.

## Lifecycle and test baseline

- `EventBus` owns a ten-worker `ThreadPoolExecutor`; `shutdown()` waits without
  a bound and is not connected to application teardown.
- `AgentScheduler` creates callbacks per topic but does not retain them, so
  unregister and shutdown cannot call the exact EventBus unsubscribe contract.
- `MainWindow.closeEvent()` cleans loaded pages but does not own process-wide
  EventBus/scheduler teardown.
- All seven tests in `tests/test_main_window_geometry.py` are skipped under
  CI/offscreen because the real window leaks EventBus threads and may SIGABRT.
  The final test also assumes the retired nested-tree sidebar.
- Phase 1 must solve the root lifecycle problem and replace these stale tests;
  Phase 0 does not alter runtime or tests.

## Product and UI baseline

The current real-shell audit used a temporary HOME/XDG profile, deterministic
fixtures, disabled background services, rejected mutating subprocesses, and
explicit dark theme.

| Step | Route | Size | Evidence SHA-256 | Baseline finding |
| --- | --- | ---: | --- | --- |
| Home | `atlas_dashboard` | 1366×900 | `baefc0e2e64bc1ed01042d09fb1fe16534ec1372b6cdd2f046420413dab35f81` | Status and attention repeat the same work; common tasks fall below the first viewport |
| Software Apps | `software:apps` | 1366×900 | `79cabfd5b80163e829c7b42a7159807ade87d2ffc58bbf32ff14ed784d04c93c` | Internal `Software_Updates` label leaks; Install/Remove copy overstates an Action Center handoff |
| System Check | `health` | 1366×900 | `dca9b518a4033b520bf0e8f01917f3eb756cb7b71d6c04f7683014a7ed07b0b9` | Route navigation and Overview/Findings/History compete |
| Activity & Recovery | `activity` | 1366×900 | `07269cbb4bbd76b07ed924603139110ef66257110fd67cfe6bc36b042abc6dd4` | Empty table and detail panels appear before activity is loaded |
| Settings | `settings` | 1366×900 | `13574c8b65b45e3219bb7c1bc7cb8d8c032420162661849cee9f03664af58c58` | Sparse layout lacks persistent saved/error feedback |
| Specialist Tools | `development` | 1366×900 | `c53e3588757c9f956c77d41adb6faf00fe65efd7c09c79193e074f419ea15464` | Long ungrouped route list is difficult to scan |
| Compact Home | `atlas_dashboard` | 900×720 | `0e641d259d2b2099ad72699e2503aec208fee6f444e8c34845ca78793090b460` | Icon rail exposes horizontal scrolling and weak search/history affordances |

Offscreen evidence does not prove compositor behavior, AT-SPI, focus order,
screen-reader output, actual system palette, or Wayland/X11 scaling. Those
remain Phase 3/4 gates.

## Compatibility classification

| Contract | Decision | Phase 0 evidence |
| --- | --- | --- |
| 81 routes, aliases, favorites, direct links | KEEP | Product contract passes |
| Action Center schema v4 and verified execution | KEEP | No execution changes in Resolve |
| System Check and journal persistence | KEEP | No new database or migration |
| CLI, JSON, API, daemon, D-Bus, support bundle | KEEP | No public interface change |
| `SectionNavigator` route navigation | KEEP | Local peer views move to a separate component later |
| Home bounded collections | ADAPT | `GuidedTask` composes existing IDs without persistence |
| Current `MainWindow` lifecycle ownership | ADAPT | Move process resources to `ApplicationRuntime` |
| EventBus and AgentScheduler cleanup | ADAPT | Exact callbacks and bounded shutdown required |
| Nested-tree geometry tests | RETIRE_PRESENTATION | Replace with current flat-shell tests |
| Historical v21 release notes | ARCHIVE | Preserved under `docs/archive/` |
| Historical v21 tags | KEEP | Legacy refs created only under release authorization |

## Phase 0 conclusion

Resolve authority, scope, measurements, compatibility decisions, tag collision,
and implementation gates are locked. Product metadata remains v20.0.0
"Continuity". No runtime product behavior, route, state, UI, test behavior,
version, tag, commit, push, or publication action is part of Phase 0.
