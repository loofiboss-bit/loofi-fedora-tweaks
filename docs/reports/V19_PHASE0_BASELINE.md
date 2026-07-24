# v19 Phase 0 Authority and Baseline

Date: 2026-07-24  
Phase: 0 — authority, baseline, and scope lock  
Runtime product changes: none

## Authority and release lineage

- The inspected checkout is `master` at
  `9cf7f520a38b089ebffc144041baebae583f4ca4`, equal to `origin/master`.
- The annotated `v18.0.0` tag peels to
  `6cfe11babd502d32bb57f333f1f505615a4f8864`.
- The historical `legacy-v18.0.0-sentinel` tag peels to
  `f0cb0bf2be8a873de368341a400186158e12498f`.
- The v18 release report records successful canonical CI `29943164246`,
  CodeQL `29943164084`, Auto Release `29943164217`, COPR `10764217`,
  checksum/SBOM/provenance readback, and a clean Fedora 44 repository install.
- v19.0.0 "Steward" is the sole active roadmap and race-lock target. Runtime,
  package, and release metadata remain at the released v18.0.0 "Haven".

The authority order for implementation is:

1. current checkout and `AGENTS.md`;
2. `ARCHITECTURE.md`;
3. the v19 canonical plan;
4. `.workflow/specs/arch-v19.0.0.md` and
   `.workflow/specs/tasks-v19.0.0.md`;
5. this inventory and current tests.

## Classification rules

- **KEEP**: preserve the current route/store and behavior.
- **ADAPT**: preserve the identity and data while composing it into System Check.
- **MIGRATE**: change schema only through an atomic, tested, read-back migration.
- **REDIRECT**: preserve the route identity but resolve it to a maintained route.
- **RETIRE_PRESENTATION**: keep compatibility identity/data but do not retain a
  separate user-facing page.

No Phase 0 item performs a runtime redirect, migration, or presentation change.

## Route and presentation inventory

Every health, Home, maintenance, diagnostics, readiness, and directly supporting
route in the current product catalog is classified below.

| Stable route | Current presentation or compatibility behavior | Classification for v19 |
| --- | --- | --- |
| `atlas_dashboard` | Canonical Home; aliases `atlas`, `atlas-home`, `fedora-control-center` | ADAPT — add explicit Check now later without startup probes |
| `dashboard` | Hidden legacy System Overview; redirects to `system_info` | REDIRECT |
| `maintenance` | Maintenance root and Updates section | KEEP |
| `maintenance:updates` | Fedora, Flatpak, and firmware update review | KEEP |
| `maintenance:cleanup` | Read-only reclaim analysis and confirmed cleanup entry | KEEP |
| `maintenance:smart-updates` | Hidden compatibility route to `maintenance:updates` | REDIRECT |
| `maintenance:health-timeline` | Visible JSON snapshot/trend page in System | ADAPT — retain ID and data; later present canonical System Check |
| `maintenance:upgrade-assistant` | Fedora release readiness and support export | KEEP — specialized follow-up, not quick check |
| `maintenance:action-center` | Sole Review/Plan/Run/Verify/History UI | KEEP |
| `maintenance:overlays` | Advanced Atomic layered-package route | KEEP |
| `monitor` | Performance and process overview | KEEP |
| `system-monitor:performance` | Performance subroute | KEEP |
| `system-monitor:processes` | Process subroute | KEEP |
| `storage` | Disk use and SMART diagnostics | KEEP — specialized SMART work stays explicit |
| `snapshots` | Recovery points | KEEP |
| `backup` | Backup tools | KEEP |
| `settings:repair` | State Doctor and Loofi state recovery | KEEP |
| `health` | Hidden legacy metric-timeline page; redirects to `diagnostics` | RETIRE_PRESENTATION — preserve route and SQLite data |
| `diagnostics` | Canonical Troubleshooting page | KEEP — specialized diagnostics remain explicit |
| `diagnostics:watchtower` | Health and troubleshooting subsection | KEEP |
| `diagnostics:boot` | Boot diagnostics | KEEP |
| `logs` | Hidden legacy route to `diagnostics:watchtower` | REDIRECT |

`core/navigation/manifest.py` remains the route/alias authority.
`canonical_persisted_route()`, `migrate_last_route()`, and
`migrate_route_references()` preserve direct links, `last_route_id`, favorites,
quick actions, unknown future favorite IDs, and current compatibility redirects.
`MainWindow.switch_to_route()` remains the runtime compatibility entry point.

## Persisted health stores

| Store | Path and schema | Current writers | Current readers | Classification |
| --- | --- | --- | --- | --- |
| Structured health snapshots | `$XDG_DATA_HOME/loofi-fedora-tweaks/health_timeline_v12.json`; `loofi.health-snapshots` schema 1; 30 snapshots | `ObservabilityService`, GUI Health Timeline, CLI `health snapshot`, daemon collection | Home, Action Center trend recommendations, workflows, API, daemon, CLI, support bundle | ADAPT — canonical System Check composes this store; no third database |
| Numeric metric timeline | `$XDG_DATA_HOME/loofi-fedora-tweaks/health_timeline.db`; `loofi.metric-timeline` schema 1; SQLite, 30-day retention | legacy Health Timeline UI and CLI `health-history record` | legacy Health Timeline UI/CLI, `ObservabilityService.status()`, state inventory and support paths | KEEP — supporting evidence remains readable in place |

The JSON store already uses an advisory lock, atomic replace, readback,
last-known-good recovery, bounded retention, redaction, and future-schema
read-only behavior. The SQLite store remains a separate numeric evidence source;
it must not become a second finding authority. No migration is authorized in
Phase 0.

Action Center plans, runs, and history remain separate schema-v3 trust records.
Finding context must not alter their digest-protected execution authority. The
Phase 1 decision on an extension-safe metadata field versus schema v4 remains
open until all v1-v3 migrations and digest inputs are inspected.

## Existing finding and recommendation identities

These IDs are compatibility input, not a new canonical v19 taxonomy.

### Home recommendation IDs

`home-source-error`, `home-stale`, `home-good`, `home-first-review`,
`state-integrity`, `action-run-review`, `pending-reboot`, `disk-pressure`,
`failed-update`, `pending-updates`, `incomplete-recovery`, `missing-backup`,
`repeated-health`, and `action-center-review`.

### Daily Maintenance card IDs

`system-updates`, `flatpak-updates`, `firmware`, `failed-services`,
`journal-warnings`, `disk-usage`, `package-health`, and `rollback`.

### Structured fingerprint kinds

`failed-service`, `journal-warning`, `low-disk`, `dnf-lock`,
`package-health`, and `missing-rollback`, plus a fallback to the source card ID.
The persisted fingerprint ID is a deterministic SHA-256-derived
`<kind>:<16 hex>` value.

### Legacy Health Registry IDs

`dnf-lock`, `failed-services`, `disk-space-root`, `pending-updates`,
`nvidia-akmods`, `atomic-pending-reboot`, `atomic-layered-packages`, and
`selinux-status`.

### Release-readiness check IDs

The current 23 IDs are `fedora-version`, `kde-plasma-version`, `qt-version`,
`session-type`, `display-manager`, `dnf5-health`, `packagekit-status`,
`dnf-locks`, `repo-health`, `third-party-repos`, `atomic-status`,
`nvidia-akmods-secureboot`, `flatpak-kde-runtimes`, `tls-cert-compat`, and the
nine `fedora45-*` preview checks. Release readiness remains a specialized route
and is not silently folded into the v19 quick profile.

## Existing finding-to-action candidates

The Action Center catalog contains 56 audited definitions. Findings do not own
commands, privilege, risk, confirmation, or verifier logic.

| Existing source | Current candidate | Boundary |
| --- | --- | --- |
| Release-readiness `repo-health` | Compatibility ID `readiness-repo-cache-clean` adapts to `dnf-clean-all` | Canonical definition and fresh preflight remain authoritative |
| Slow-system failed unit | `restart-failed-service` with a validated unit parameter | Navigation/preselection only until the user creates and confirms a plan |
| Reclaimable Traditional package cache | `dnf-clean-all` | Atomic path is manual-only |
| Supported filesystem trim guidance | `fstrim-all` | Existing definition rechecks applicability |
| Observability trend fingerprints | Dynamic `recommendation-<fingerprint>` items | Manual-only; no command preview or executable mapping |
| Home recommendations | Route IDs only | No direct action ID and no execution |

The legacy task dashboard also names `dnf-clean-all`, `fstrim-all`, and
`restart-failed-service`; its gaming action strings are not canonical catalog
definitions and must not be promoted by v19. Phase 1 must validate every new
mapping against `ActionCatalog` and reject unknown, manual-only, or
variant-inapplicable mappings.

## Deterministic Home state baseline

The current `HomeService` behavior was exercised with isolated in-memory source
fixtures and the same cases covered by `tests/test_home_service.py`.

| Case | `data_state` | `overall_state` | Primary recommendation | Four status areas |
| --- | --- | --- | --- | --- |
| Empty | `empty` | `attention` | `home-first-review` / `first_health_review` | all `unknown` |
| Fresh, no finding | `fresh` | `good` | `home-good` / `no_action` | health `good`; others `unknown` without explicit payloads |
| Stale | `stale` | `attention` | `home-stale` / `stale_data` | health `attention`; others not promoted to good |
| Partial collector error | `error` | `attention` | `home-source-error` / `source_error` | successful snapshot remains readable; health is not all-clear |
| Critical state finding | `fresh` | `critical` | `state-integrity` / `state_integrity` | health `critical` |

Home reads saved state only. It has no polling timer and performs no probe or
mutation during cold startup.

## Collector-duration baseline

There is no canonical v19 quick-check service yet. The closest current
read-only path is `DailyMaintenanceService.collect()`. Three sequential live
runs on the inspected Fedora 44 Traditional host produced these wall times:

| Current collector step | Median ms | Observed range ms | Phase 1 budget ceiling |
| --- | ---: | ---: | ---: |
| Fedora variant | 0.003 | 0.002–0.081 | 50 |
| Package health probes | 207.049 | 159.588–239.938 | 500 |
| System-update card synthesis | 0.008 | 0.007–0.009 | 50 |
| Flatpak remote probe | 15.137 | 13.922–19.354 | excluded from quick profile |
| Firmware availability | 0.113 | 0.081–0.156 | excluded from quick profile |
| Failed services | 54.988 | 53.400–55.695 | 250 |
| Journal warnings | 233.609 | 23.020–2,156.772 | excluded from quick profile |
| Root filesystem | 3.081 | 2.263–3.687 | 100 |
| Package-health card synthesis | 0.007 | 0.004–0.008 | 50 |
| Recovery/rollback availability | 0.090 | 0.067–0.113 | 250 |
| Total legacy collection | 551.860 | 252.370–2,438.079 | 3,500 |

The proposed quick profile excludes Flatpak, firmware, and journal collection.
Phase 1 must add separately measured budgets for state integrity and existing
Action Center state reads, preserve partial successes on timeout, and keep every
probe within its existing hard timeout.

## Startup, memory, and screenshot baseline

The public v18 release benchmark remains the release authority: meaningful Home
median **142.042 ms**, median RSS **75,408 KiB**, and release ceilings of
**172.618 ms** and **86,466 KiB**.

Two new offscreen 10-run series on 2026-07-24 measured:

| Series | Meaningful Home median | Median RSS | Structural contract |
| --- | ---: | ---: | --- |
| 1 | 221.000 ms | 76,274 KiB | 1 provider; 0 probes, timers, QThreads |
| 2 | 190.240 ms | 76,166 KiB | 1 provider; 0 probes, timers, QThreads |

The host used the `powersave` CPU governor with active desktop load, so these
timings are recorded as environment-sensitive local evidence, not a replacement
for the exact-release result. The structural startup gate passed. Any v19
runtime phase must re-establish a comparable idle-host timing before claiming
the v18 latency ceiling.

The repository has 16 user-guide PNGs. The current Home baseline is
`docs/images/user-guide/home-dashboard.png`, 1,400 × 900,
SHA-256 `1bd4487cfb759e55f2b6f8daee31be130576ecd3ab75bed02585331413f31536`.
It records the empty Home state with four unavailable statuses and a
navigation-only Review action. The v18 public report separately records
post-publication wiki readback of 20 synchronized screenshots; that public
claim is not converted into additional local files.

## Fedora support evidence boundary

- **Traditional Fedora 44:** v18 was physically verified on Fedora KDE 44,
  kernel `7.1.4-202.fc44.x86_64`, Plasma/KWin `6.7.3`, PyQt `6.11.0`, native
  Wayland at 1,920 × 1,080 and 1.4 scale, plus XCB/XWayland at 1,180 DIP.
- **Atomic Fedora 44:** the physical-image install, staged rpm-ostree
  deployment, reboot, and checksum readback are carried forward from the v17
  Kinoite 44.1.7 KVM evidence. v18 reran the current Atomic contract matrix but
  did not perform a fresh v18 guest installation.
- **Fedora 45:** preview-only. No stable-support claim or certification is
  carried forward.
- **Firmware:** signed v17 fwupd emulation is carried forward; there is no fresh
  v18 physical-device claim.

v19 must not describe carried-forward Atomic or firmware evidence as fresh
Steward certification.

## Phase 0 verification

The pre-edit v18 baseline passed:

```text
check_release_docs.py                 OK
project_stats.py --check              OK
sync_ai_adapters.py --check           OK
check_stabilization_rules.py          OK
validate_v18_haven.py                 OK (80 routes)
validate_v18_architecture.py          OK
```

The Phase 0 closeout uses the version-neutral validator entry points and keeps
the v18 filenames as thin compatibility wrappers. No runtime source, route,
schema, product version, package metadata, tag, or remote service is changed.
