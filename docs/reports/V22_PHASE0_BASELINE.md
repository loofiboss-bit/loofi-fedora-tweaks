# V22 Phase 0 Baseline and Scope Lock

Date: 2026-07-28  
Baseline commit: `3c9ce62a14839f40dd1ac027cc43a83476f27571`  
Exact product tag: `v21.0.0`  
Active target: `v22.0.0 "Alignment"`

## Authority and release state

- `master` matched `origin/master` with a clean worktree at baseline.
- V21 is complete and public. Its release commit, CI, CodeQL, COPR, clean
  Fedora 44 installation, documentation, and lineage readback remain recorded
  in `V21_RELEASE_PUBLICATION.md`.
- V20 remains historically publication-blocked. V22 does not reopen or infer
  completion for that lineage.
- No V22 plan, architecture, task contract, or race lock existed before this
  phase.
- Product metadata remains v21.0.0. Phase 0 performs no runtime, route, state,
  UI, version, tag, commit, push, install, or publication action.

## Repository and quality baseline

- 1,424 tracked files, 401 production Python files, and 312 test modules.
- The product validator reports 81 stable routes, classified actions,
  built-in-only plugins, and guarded entrypoints.
- Architecture, release-document, requirements-sync, and packaging-manifest
  validation pass.
- The current full verification result is 6,863 passed tests, 61 skipped tests,
  1,057 passed subtests, 20 non-failing warnings, and 86.43 percent coverage.
- The largest current Python modules are:
  - `core/product_catalog_records.py` — 76,275 bytes
  - `core/actions/assurance.py` — 54,015 bytes
  - `ui/main_window.py` — 43,347 bytes
  - `core/diagnostics/release_readiness.py` — 42,486 bytes
  - `cli/main.py` — 40,594 bytes
  - `ui/monitor_tab.py` — 40,556 bytes

## Runtime and performance baseline

The committed summary in `V22_PHASE0_STARTUP.json` uses a temporary standard
profile, Qt offscreen, two warmups, and seven measured runs:

- meaningful Home median: 162.010 ms;
- `MainWindow` median: 159.734 ms;
- RSS median: 76,372 KiB;
- one realized Home provider;
- zero subprocess probes, active timers, and running QThreads.

The V22 ceilings are 178.211 ms for meaningful Home and 84,009 KiB RSS,
calculated as Phase 0 × 1.10.

## Visual baseline

The current-shell audit used a temporary HOME/XDG profile, deterministic data,
disabled background services, rejected mutating subprocesses, and Qt offscreen.

| Step | Evidence SHA-256 | Baseline finding |
| --- | --- | --- |
| Home wide | `266e09cded28c9502d652a88126708d0a34d424e4155c1ef59210684dc49f481` | Correct bounded content, but status/cards have equal visual weight |
| Home compact | `6a0702812a768ed1d8b14fcae2924257706a804b2ac3b827bf86ddd68aed10b0` | Primary task is clear; secondary content drops below the first viewport |
| System Check | `0509f5ab31444c886a435b702abca4b458d660b5e0162fba820ce9083b815fd7` | Route, section, and local-view navigation compete |
| Action Center | `254ce30f6566b8a910a993175ca6b44a67a47835d6ef7ab9e9424dbcbbc098b7` | Safe lifecycle, but too many equally prominent controls |
| Settings | `87bd88ec5ecad97218ceb61932f9e50fc97967409df726ca56dfc869dd528646` | Consistent feedback; visually sparse |
| Specialist Tools | `63c69ba6085ec8822ab7b0eb1252b778dc6b13f5a10856b29381d044f880e910` | Searchable but still a long route rail |
| Activity & Recovery | `3535423724188fe01ecffed2f6a57418ad250df8dce6f56571d5fb2d9a22404e` | Truthful empty state with weak spatial focus |

Offscreen evidence does not prove compositor behavior, real focus order, Orca
speech, host palette, Wayland scaling, or physical Atomic behavior.

## Trust findings locked for Phase 1

- COPR workflows can treat artifacts as final evidence before API success and
  downgrade a failed clean installation to a warning.
- API and daemon RPM subpackages omit required multipart and PyGObject runtime
  dependencies.
- Delivered Flatpak checks contain shell-pipe syntax while execution correctly
  uses `shell=False`.
- ApplicationRuntime passes remaining time to a synchronous cleanup callback
  but cannot enforce the bound.
- Shared support-data redaction misses Authorization Bearer and colon-separated
  credential forms.

## Compatibility classification

| Contract | Decision |
| --- | --- |
| 81 routes, aliases, favorites, direct links | KEEP |
| Action Center schema v4 and execution lifecycle | KEEP |
| System Check and journal persistence | KEEP |
| CLI, JSON, API, daemon, D-Bus, support bundle | KEEP |
| Traditional/Atomic policy | KEEP |
| Home bounded collections and one-provider startup | KEEP |
| Product catalog storage layout | ADAPT behind equality tests |
| ApplicationRuntime cleanup protocol | ADAPT to enforceable two-phase stop |
| Plasma-owned setting duplication | ADAPT through inert native handoffs |
| Specialist Tools physical RPM split | BLOCKED / OUT OF SCOPE |

## Phase 0 conclusion

Alignment authority, baseline, protected contracts, and implementation gates
are locked. Product metadata remains v21.0.0 "Resolve". Phase 1 may start only
after the Phase 0 documentation, product, architecture, and workflow-lock gates
pass.
