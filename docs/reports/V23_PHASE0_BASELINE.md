# V23 Phase 0 Baseline and Scope Lock

Date: 2026-07-29  
Baseline commit: `5bd323b6794c72bb17390149a4e07bff3e35bf35`  
Current product and public release: `v22.0.0 "Alignment"`  
Active implementation target: `v23.0.0 "Compass"`

## Outcome

Compass authority, the exact v22 starting point, protected contracts, relevant
interfaces, source ownership, performance, and current visual state are locked.
The existing `diagnostics` route is selected as the future canonical
Troubleshoot surface.

Phase 0 changes documentation, workflow authority, evidence, tests, and
development-only capture/benchmark tooling. It does not add troubleshooting
runtime code, change product behavior, alter a route or schema, change product
metadata, install a package, or modify a remote service.

## Checkout and worktree authority

- `master` matched `origin/master` at the baseline commit with a clean worktree
  and no ahead/behind commits.
- The baseline contains 1,461 tracked files, 414 production Python files, and
  319 test modules.
- Phase 0 changes remain uncommitted in the worktree. No pre-existing user
  changes were present or overwritten.
- Product metadata, RPM spec metadata, and `pyproject.toml` remain v22.0.0
  "Alignment".
- The product-contract validator reports 81 ordered stable routes and 63
  classified first-party Action Center definitions.
- V20 remains historically `PUBLICATION BLOCKED`.

## Current release, CI, COPR, and package state

Read-only public and host checks were performed on 2026-07-29. They confirm:

- annotated tag object `dc0d8e46442f46669b65451f0aae4b4fecb0e777`
  for `v22.0.0` peels to release commit
  `31dc3ac7af53367f2bd257336ad0282cadea5fe7`;
- the GitHub release is public, non-draft, non-prerelease, and exposes exactly
  the eight V22 assets recorded in `V22_RELEASE_PUBLICATION.md`;
- Auto Release Pipeline `30375621830`, CI `30375622954`, and CodeQL
  `30375619797` are completed with `success` for the exact release commit;
- COPR build `10783672` remains in terminal API state `succeeded` for source
  EVR `1:22.0.0-1` and `fedora-44-x86_64`;
- the host already had the base, API, and daemon packages installed as
  `1:22.0.0-1.fc44 noarch`, and both installed entrypoints report `22.0.0`;
- no package was installed, upgraded, removed, or verified with a mutating
  package operation during Phase 0; and
- the GitHub repository had no open issues or pull requests at readback time.

This readback confirms the starting point. It does not republish V22 and is not
future Compass release evidence.

## Historical `v23.0.0` collision

The annotated `v23.0.0` tag already exists locally and on origin:

- tag object: `496ab1edb608a7420083b6541ddbc61b64a432f0`;
- peeled commit: `adc4cef116d147bd5b845f0ec98c3a1970b8b054`;
- historical subject: `release: v23.0.0 architecture hardening`;
- GitHub Release: none.

Phase 0 preserves this lineage. No tag was moved, deleted, replaced, pushed, or
published. Compass release naming and historical-tag preservation remain a
separately authorized Phase 6 blocker.

## Canonical GUI route inventory

| Route | Current owner | Current role | Compass decision |
| --- | --- | --- | --- |
| `atlas_dashboard` | Home / `atlas_dashboard` | Saved-state summary and explicit System Check start | KEEP; never starts troubleshooting |
| `health` | System / `health` | Current System Check overview and findings | KEEP |
| `maintenance:health-timeline` | System / `health` | System Check history view | KEEP |
| `diagnostics` | System / `diagnostics` | Discoverable Troubleshooting entry | SELECT as canonical Troubleshoot surface |
| `diagnostics:watchtower` | System / `diagnostics` | Existing health/troubleshooting view | KEEP as same-plugin route |
| `logs` | System / `logs` | Compatibility system-log route | KEEP redirect to `diagnostics:watchtower` |
| `diagnostics:boot` | System / `diagnostics` | Advanced Boot view | KEEP |
| `activity` | System / `activity` | Trusted Change Journal and recovery guidance | KEEP as source-owned history |
| `maintenance:action-center` | Software & Updates / `maintenance` | Review, apply, and verify one action | KEEP as sole execution authority |
| `maintenance:upgrade-assistant` | Software & Updates / `maintenance` | Release-readiness diagnostics | KEEP as source-owned readiness surface |

Supporting evidence routes such as `monitor`, `system-monitor:performance`,
`storage`, `network`, `maintenance:updates`, and `maintenance:cleanup` remain
separate current owners. Compass may navigate to them but may not duplicate or
silently execute their behavior.

## CLI, API, and support-export inventory

### CLI

- System Check: `health check`, `health findings`, `health comparison`,
  `health history`, `health snapshot`, and `health timeline`.
- Saved maintenance: `maintenance today`.
- Trusted Change Journal: `activity list`, `activity show`,
  `activity related`, and `activity recover`.
- Diagnostics and export: `doctor`, `support-bundle`, `readiness`, and
  `readiness export`.
- Action Center: `action-center list|preview|history|recommendations|plan|show|apply|verify`.
- Global JSON remains `loofi --json ...`; the default operation timeout remains
  300 seconds.

Phase 0 adds no `troubleshoot` CLI command.

### Authenticated loopback API

Relevant existing retrieval routes are:

- `GET /api/health`;
- `GET /api/observability/current`;
- `GET /api/observability/timeline`;
- `GET /api/observability/status`;
- `GET /api/state/status`;
- `GET /api/system-check/latest`;
- `GET /api/activity`;
- `GET /api/activity/{event_id}`;
- `GET /api/action-center/plans` and `GET /plans/{plan_id}`; and
- `GET /api/action-center/runs` and `GET /runs/{run_id}`.

The API exposes no System Check or troubleshooting collection, confirmation,
plan creation, execution, verification, or support-export mutation route.

### Support export

- `SupportBundleWriter` is the canonical v12 writer.
- Supported import versions remain v2-v12.
- The v12 writer extends the v11 bounded System Check payload with at most 50
  redacted Trusted Change Journal events and source readiness.
- The Diagnostics page and `support-bundle` CLI use the existing export
  boundary; `readiness export` remains a separate explicit CLI export.
- No API support-export endpoint exists.

## Collector and timeout inventory

| Owner | Existing source | Bound | Notes |
| --- | --- | ---: | --- |
| System Check | `state-integrity` | 20 s | Existing State Doctor |
| System Check | `maintenance` | 45 s | Closed quick Daily Maintenance subset |
| System Check | `storage-reclaim` | 25 s | Existing read-only reclaim analysis |
| System Check | `action-center` | 10 s | Read-only plan/run state |
| System Check | `pending-reboot` | 20 s | Traditional/Atomic-specific state |
| Change Journal | DNF5, rpm-ostree, Flatpak, fwupd command adapters | 15 s each | Classified read-only `CommandFacade` vectors |
| Change Journal | Action Center and Loofi history | local read | Read-only store methods; no command |
| Change Journal | cache / correlation | 15 s / 7 days | Bounded in-memory cache and related-change window |
| Daily Maintenance | failed services / journal / root filesystem | 10 s / 10 s / 8 s | Direct read-only subprocess probes |
| DNF5 health | PackageKit / lock holder / repository | 5 s / 5 s / 20 s | Structured package-health report |
| Reclaim analysis | package cache / journal size | 10 s each | Read-only measurement |
| Network | active connection and DNS | 5 s each | Eligible evidence; mixed mutators in the current class must not leak into adapters |
| Boot analysis | boot stats, slow services, suggestions | 30 s each | Existing read-only utility; raw output requires bounded structuring before persistence |

Current Diagnostics widgets also own synchronous journal and boot probes. They
are evidence of the surface being adapted, not a domain pattern to copy.
Phase 1/2 must put any reused probe behind the PyQt-free bounded domain and
must not run it during page construction.

## Stores and schema inventory

| Store or contract | Current schema / limit | Compass boundary |
| --- | --- | --- |
| Health snapshots / System Check envelope | schema v1, 30 snapshots | Reuse; no new health store |
| System Check result | schema v1 | Reuse principles; do not rewrite history |
| System Check comparison | schema v1 | Extend principles, keep source/variant compatibility |
| Metric timeline | schema v1 SQLite, 30 days | Read existing database only |
| Trusted Change Journal | `loofi.change-journal/v1`, max 500 composed events | Source-owned, no new journal database |
| Action plans | schema v4, max 50 | Read-only composition; Action Center remains owner |
| Action runs | schema v4, max 100 | Read-only composition; `verified` is not `resolved` |
| Support bundle | current v12, readers v2-v12 | Advance only in Phase 4 |
| Settings and XDG state | existing state inventory and atomic I/O | Future session JSON must register and fail closed on future schemas |

The historical XDG inventory still names legacy action-plan/run schema metadata
while the canonical stores are v4. Phase 0 records this discrepancy but does
not change runtime schema behavior. Any correction must be covered by a
separately authorized implementation phase and migration/readback tests.

## Command, worker, and timer boundaries

- `CommandFacade` is the existing classified read-only command boundary for
  Trusted Change Journal command sources.
- Daily Maintenance, DNF5 health, reclaim, network, journal, and boot utilities
  contain timeout-bounded direct probes. Only closed read-only calls may be
  adapted; mixed mutators and raw output are not eligible session data.
- Action Center is the sole host mutation authority. A troubleshooting finding
  may reference one existing action ID but never persist or execute its command.
- `SystemCheckWorker` is the explicit cancellable `BaseWorker` adapter; the
  service uses at most four executor threads for its five bounded collectors.
- `ActivityJournalWorker` runs only after explicit load/refresh.
- Action Center owns a transient operation `QThread` only for an explicit
  lifecycle operation.
- Home uses one zero-delay `QTimer.singleShot` to load saved state. The Phase 0
  startup evidence found no active timer or running QThread after Home became
  meaningful.
- No background troubleshooting worker, timer, poller, or session exists.

## Closed-profile source feasibility

No Compass profile exists at runtime in Phase 0. The inventory classifies
whether existing evidence can support a future bounded adapter:

| Profile | Existing usable evidence | Phase 0 decision |
| --- | --- | --- |
| `system_slow` | saved metrics/trends, failed services, System Check, package/deployment changes | Adapter-ready; no new background collection |
| `updates_failed` | DNF5 health/locks/repos, pending deployment/reboot, change journal, Action Center runs | Adapter-ready with strict Traditional/Atomic branching |
| `application_failed` | package/Flatpak presence and related package/Flatpak history | REDUCE: no safe closed application-journal collector exists; do not launch arbitrary processes or persist broad journal output |
| `network_problem` | active NetworkManager connection and DNS metadata | REDUCE: isolate read-only metadata from mixed mutators; no Wi-Fi/network scan or unbounded connectivity probe |
| `storage_pressure` | root usage, reclaim analysis, saved metrics, package/Flatpak activity | Adapter-ready |
| `boot_or_deployment` | boot identity/timing, failed units, pending reboot, rpm-ostree deployment and firmware history | Adapter-ready after raw boot/service output is normalized and bounded |

Unavailable required evidence must yield `partial` or `unavailable`, never an
all-clear. Phase 0 adds none of these adapters.

## Performance and resource baseline

The retained `V23_PHASE0_STARTUP.json` uses a temporary Standard profile, Qt
offscreen, two warmups, and seven measured runs:

- meaningful Home median: 172.562 ms;
- `MainWindow` median: 169.996 ms;
- RSS median: 76,472 KiB;
- one realized `atlas_dashboard` provider;
- zero cold-start subprocess probes;
- zero active timers and running QThreads; and
- no System Check runtime imports.

The Compass Phase 0 × 1.10 ceilings are 189.819 ms for meaningful Home and
84,120 KiB RSS.

The retained `V23_PHASE0_SYSTEM_CHECK.json` uses five non-persisting reads:

- total median: 213.511 ms against 3,500 ms;
- state-integrity: 60.727 ms against 250 ms;
- maintenance: 212.356 ms against 1,200 ms;
- storage-reclaim: 55.448 ms against 500 ms;
- action-center: 11.390 ms against 250 ms; and
- pending-reboot: 0.139 ms against 250 ms.

All five runs completed on the current Traditional host without source errors.
This is read-only local timing, not Atomic or physical release qualification.

## Deterministic visual baseline

`scripts/capture_v23_phase0.py` rendered the real lazy `MainWindow` with a
temporary HOME/XDG profile, disabled background services, rejected
asynchronous commands, rejected mutating subprocesses, Qt offscreen, and
Standard navigation.

The 12-frame matrix covers wide 1366×900 and compact 860×720 views of:

- Home;
- Troubleshooting (`diagnostics`);
- System Check;
- Activity & Recovery;
- Action Center; and
- Release Readiness.

`V23_PHASE0_SCREENSHOTS.json` retains every raw-frame digest and six two-frame
contact sheets under `docs/images/v23/phase0/contact-sheets/`. Raw frames are
transient by default. Offscreen evidence does not prove Wayland, real focus
order, Orca speech, live AT-SPI nodes, host palette behavior, or physical
Traditional/Atomic results.

## Validation

The final Phase 0 validation set covers:

- focused Compass authority and evidence tests;
- route/catalog and support-redaction regressions;
- full lint, mypy, architecture, test, subtest, and coverage verification;
- release-document, version, product, System Check, packaging, statistics, and
  generated-adapter validation;
- startup, System Check, and screenshot evidence readback; and
- JSON parsing plus `git diff --check`.

The completed local verification produced:

- `just verify`: 6,916 passed, 61 skipped, 1,079 subtests passed, 20 warnings,
  86.66% total coverage, and all lint, mypy, architecture, and test checks
  passed;
- focused Phase 0, startup, System Check, support-bundle, observability,
  redaction, and change-journal tests: 30 passed;
- expanded support-export and redaction regression set: 21 passed; and
- all release-document, product-contract, architecture, System Check,
  packaging, statistics, generated-adapter, evidence-readback, JSON, and diff
  validators passed.

The warnings are pre-existing deprecation, resource, and mocked-thread warnings;
they did not fail the suite. No physical or external release gate is marked
passed by these local checks.

## Remaining blockers

- The historical `v23.0.0` tag collision requires a separate release-lineage
  decision and authorization.
- `application_failed` lacks a safe closed application-journal collector.
- `network_problem` requires a read-only adapter that excludes existing scan
  and mutation methods.
- The XDG inventory's legacy Action Center schema metadata must not be changed
  without runtime migration/readback analysis.
- All Phase 1-6 implementation work remains not started.
- Physical Fedora 44 Wayland, keyboard, Orca/AT-SPI, Traditional, and fresh
  Kinoite/Atomic qualification remains unverified for Compass.
- No Compass commit, exact-candidate artifacts, signing, GitHub/COPR action,
  host installation, or public readback exists.

## Phase 0 conclusion

All locally possible Phase 0 authority, inventory, measurement, documentation,
and evidence tasks are complete. Product metadata remains v22.0.0 "Alignment";
the 81-route product and existing runtime contracts are unchanged. Phase 1 was
not started.
