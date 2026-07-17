# v15 Phase 0 Baseline — v14.0.0 "Helm"

**Status:** Complete
**Measured:** 2026-07-17
**Scope:** Phase 0 evidence and classification only
**Production code changed:** No
**Version changed:** No
**Phase 1 started:** No

## 1. Outcome and authority

Phase 0 confirms that v15.0.0 "Essentials" must begin with top-level plugin
loading and startup deferral before rebuilding the application shell. The live
v14 application eagerly imports and constructs all built-in plugins, performs
specialist probes, starts hidden-page timers and background threads, and only
then renders Home.

The verified Git state is:

| Authority | Commit | Result |
| --- | --- | --- |
| Current `master` and `origin/master` | `33f37ec48dea8dee36e69703dd4e71915756e116` | Clean and synchronized |
| v14.0.0 annotated tag target | `4f0c09174e0c1a7abe0e09f810795ea2f8d3a830` | Exact tag baseline |
| Reviewed post-release `master` | `fe774cfa9f0916a9214a42a3c1125a26680e0351` | Ancestor of current HEAD |

The two post-tag commits before the reviewed post-release state are release
workflow/documentation closure commits. Current HEAD adds only
`docs/plans/LOOFI_FEDORA_TWEAKS_V15_PLAN.md` relative to `fe774cf`; it does not
change the v14 product implementation. The commit subject at HEAD is therefore
not used as evidence of a product change.

Reproduction commands:

```bash
git status --short --branch
git rev-parse HEAD
git rev-parse v14.0.0^{}
git merge-base --is-ancestor fe774cfa9f0916a9214a42a3c1125a26680e0351 HEAD
git diff --name-status fe774cfa9f0916a9214a42a3c1125a26680e0351..HEAD
just version
```

## 2. Test environment and installed packages

| Item | Baseline |
| --- | --- |
| Fedora | Fedora Linux 44, KDE Plasma Desktop Edition |
| Kernel | `7.1.3-201.fc44.x86_64` |
| Plasma | `6.7.2` |
| Session | KDE Wayland host; benchmark used Qt offscreen rendering |
| Python | `3.14.6` |
| PyQt / Qt | `6.11.0` / `6.11.0` |
| Source version | `14.0.0 "Helm"` |
| Installed base RPM | `loofi-fedora-tweaks-14.0.0-1.fc44.noarch` |
| API subpackage | Not installed |
| Daemon subpackage | Not installed |

Environment commands:

```bash
cat /etc/os-release
uname -a
plasmashell --version
python3 --version
python3 -c 'import PyQt6.QtCore as q; print(q.PYQT_VERSION_STR, q.QT_VERSION_STR)'
rpm -q loofi-fedora-tweaks loofi-fedora-tweaks-api loofi-fedora-tweaks-daemon
```

The base RPM owns the complete application tree under
`/usr/lib/loofi-fedora-tweaks`. The existing `-api` and `-daemon` RPMs package
their service units and depend on the base package. There is no physical
`-extras` or `-devel` subpackage. The base package still requires the emoji font
and describes specialist AI, developer, virtualization, mesh, and teleport
features as core capability.

## 3. Startup measurement

### 3.1 Method

Ten separate Python processes were measured after one discarded warm-up. Each
recorded process used:

```text
PYTHONPATH=loofi-fedora-tweaks
QT_QPA_PLATFORM=offscreen
experience_level=beginner
favorites=[]
guided_tour=disabled in the measurement harness
```

The harness used clean in-memory settings and an empty temporary favorites path;
it did not alter the user's persisted configuration. It wrapped
`subprocess.run` to record probes, created `QApplication` and `MainWindow`, and
processed Qt events until the `atlas_dashboard` `LazyWidget` had realized its
actual `AtlasDashboardTab`. That event is the **first meaningful Home render**.
RSS came from `/proc/self/status` at the same marker.

The offscreen method is the reproducible comparison baseline for v15. Final v15
measurements must use the same machine, profile, launch method, milestone, and
commands. These numbers are not presented as compositor-inclusive Wayland
latency.

### 3.2 Raw launches

All times are milliseconds from benchmark process entry. RSS is KiB.

| Run | GUI import | MainWindow built | `show()` returned | Meaningful Home | RSS |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 274.884 | 5173.723 | 5176.177 | 5181.762 | 107508 |
| 2 | 137.571 | 5090.021 | 5092.523 | 5097.271 | 106768 |
| 3 | 174.412 | 4398.661 | 4402.203 | 4410.881 | 107608 |
| 4 | 166.777 | 4496.747 | 4499.104 | 4503.718 | 107720 |
| 5 | 121.540 | 4055.231 | 4058.160 | 4063.653 | 107580 |
| 6 | 146.231 | 4471.843 | 4474.229 | 4478.997 | 106836 |
| 7 | 132.733 | 4444.188 | 4447.392 | 4453.596 | 107812 |
| 8 | 159.685 | 4971.374 | 4973.776 | 4978.284 | 106976 |
| 9 | 129.447 | 4592.688 | 4595.591 | 4600.687 | 106892 |
| 10 | 152.034 | 4728.911 | 4731.358 | 4736.232 | 107384 |
| **Median** | **149.132** | **4544.718** | **4547.347** | **4552.202** | **107446** |
| **Range** | **121.540–274.884** | **4055.231–5173.723** | **4058.160–5176.177** | **4063.653–5181.762** | **106768–107812** |

### 3.3 Imports and object construction

The following counts were stable across all ten launches:

- 527 imported modules.
- 38 imported `ui` modules.
- 30 imported `ui.*_tab` modules.
- 29 built-in plugin instances registered eagerly.
- 14 plugin rows visible in Beginner mode.
- 2,425 live Qt widgets and 59 top-level widgets at first Home render.

`PluginLoader.load_builtins()` imports every module in `_BUILTIN_PLUGINS` and
instantiates its class before `MainWindow` wraps the already-created plugin in a
`LazyWidget`. The existing wrapper defers parenting/display, not module import,
constructor work, probes, timers, or threads. This is the primary startup
architecture defect.

### 3.4 Timers and threads

Nine timers were active at first Home render:

| Interval | Owner/behavior |
| ---: | --- |
| 1 s | Hidden System Monitor performance collector |
| 2 s | Hidden Live Overview fast dashboard refresh |
| 3 s | Hidden System Monitor process refresh |
| 5 s | Hidden Hardware refresh |
| 5 s | MainWindow notification badge polling |
| 10 s | Hidden Agents refresh |
| 10 s | Hidden Live Overview slow dashboard refresh |
| 30 s | Hidden Performance workload detection |
| 30 s | MainWindow sidebar status refresh |

Three `QThread` objects existed: `PulseThread` and `FetchMarketplaceThread` were
running, while `AppConfigFetcher` had completed. Python exposed the main thread
plus the Qt worker wrapper. Hidden page timers and optional marketplace work
must not run before activation in v15.

### 3.5 Startup probes

There were 54 recorded subprocess calls representing 47 unique command vectors
before meaningful Home. The stable binary distribution was:

| Binary | Calls | Startup source/impact |
| --- | ---: | --- |
| `lspci` | 24 | Eager hardware inventory |
| `systemctl` | 8 | Services, daemon, gaming, firewall checks |
| `systemd-analyze` | 5 | Eager boot diagnostics; repeated vectors |
| `ss` | 4 | Eager network/security inspection; repeated vectors |
| `mokutil` | 3 | Eager Secure Boot/MOK inspection |
| `journalctl` | 2 | Eager diagnostics; same vector repeated |
| `virsh` | 2 | Eager virtualization inspection |
| `zramctl` | 2 | Eager diagnostics |
| `dnf` | 1 | `dnf check-update --quiet` |
| `powerprofilesctl` | 1 | Eager power profile check |
| `rustup` | 1 | Eager development-tool check |
| `arecord` | 1 | Eager audio check |

Repeated vectors included `systemd-analyze blame` three times and duplicate
`systemd-analyze`, `journalctl`, `ss`, and firewalld checks. Pulse also registers
DBus listeners unconditionally during `MainWindow` construction. Phase 2 must
move these probes behind route activation or explicit asynchronous Home data
requirements.

## 4. Navigation, modes, and screenshot evidence

The PyQt-free route manifest contains 78 canonical IDs: 29 top-level plugin
routes and 49 subroutes. No duplicate route IDs were found. Route metadata
contains 17 Beginner, 27 Advanced, and 34 all-level entries; risk metadata
contains 58 none, 18 medium, and 2 high entries.

The current route namespace is an established compatibility contract. v15 will
add destination/section mapping and policy outcomes; it will not replace these
IDs.

The complete canonical ID inventory is:

| Kind | Count | IDs |
| --- | ---: | --- |
| Top-level plugin routes | 29 | `atlas_dashboard`, `dashboard`, `system_info`, `monitor`, `community`, `agents`, `software`, `maintenance`, `snapshots`, `hardware`, `performance`, `storage`, `gaming`, `network`, `mesh`, `security`, `backup`, `desktop`, `profiles`, `extensions`, `settings`, `development`, `ai_lab`, `automation`, `health`, `logs`, `diagnostics`, `teleport`, `virtualization` |
| Subroutes | 49 | `system-monitor:performance`, `system-monitor:processes`, `community:presets`, `community:marketplace`, `community:plugins`, `community:featured`, `agents:dashboard`, `agents:my-agents`, `agents:create`, `agents:activity`, `software:apps`, `software:repos`, `software:flatpak`, `maintenance:updates`, `maintenance:cleanup`, `maintenance:smart-updates`, `maintenance:health-timeline`, `maintenance:upgrade-assistant`, `maintenance:action-center`, `maintenance:overlays`, `network:connections`, `network:dns`, `network:privacy`, `network:monitoring`, `loofi-link:devices`, `loofi-link:clipboard`, `loofi-link:file-drop`, `security:overview`, `security:firewall`, `security:privacy`, `security:ports`, `desktop:director`, `desktop:theming`, `desktop:display`, `settings:appearance`, `settings:behavior`, `settings:advanced`, `development:containers`, `development:developer`, `ai-lab:models`, `ai-lab:voice`, `ai-lab:knowledge`, `automation:scheduler`, `automation:replicator`, `diagnostics:watchtower`, `diagnostics:boot`, `virtualization:vms`, `virtualization:gpu-passthrough`, `virtualization:disposable` |

| Mode | Visible top-level areas | Visible plugin rows |
| --- | ---: | ---: |
| Beginner | 5 | 14 |
| Intermediate | 5 | 21 |
| Advanced | 6 | 28 |

The three captures were generated at 1280×720 using the same offscreen source
checkout. They are intentionally outside the repository because this Phase 0
allows only the report file to change.

| Mode | Local evidence | Dimensions | SHA-256 |
| --- | --- | ---: | --- |
| Beginner | [`/tmp/loofi-v15-phase0-beginner.png`](/tmp/loofi-v15-phase0-beginner.png) | 1280×720 | `84a1c81ba74a8ba6e60dd207e5cbc506fe00782cc33678fe843157ac3c90e551` |
| Intermediate | [`/tmp/loofi-v15-phase0-intermediate.png`](/tmp/loofi-v15-phase0-intermediate.png) | 1280×720 | `e283bf93a5e7bc90c908ca8e2b7aa2c752c17ba47c15fac049cb12da2d7bd60d` |
| Advanced | [`/tmp/loofi-v15-phase0-advanced.png`](/tmp/loofi-v15-phase0-advanced.png) | 1280×720 | `182e6b8aa99cec2ea21a18a937c72492f5408f7b20b6a2b40a9b288b74554006` |

Visual review confirms:

- Home is the same content in all three modes, while navigation density grows.
- The shell is an expandable area/plugin tree, not a flat destination list.
- Intermediate and Advanced require scrolling at 1280×720.
- Version `v14.0.0` appears in the page title, sidebar footer, status footer, and
  window title.
- Permanent shortcut/status chrome remains visible while idle.
- Home contains four separate route cards plus seven task cards rather than one
  prioritized recommendation model.

## 5. Current product inventory

### Home and shell

- `atlas_dashboard` is the visible Home and must remain the canonical identity.
- `dashboard` is a second full live Home implementation, hidden in the default
  sidebar but still routable and eagerly constructed.
- Sidebar search, the command palette, and the quick-action dialog are separate
  discovery implementations.
- Favorites can create another sidebar category and override experience-level
  visibility.
- The sidebar is an expandable five-area tree plus the Advanced `More` area.
- The shell permanently constructs duplicate version/footer/status labels,
  shortcut hints, a notification bell, tray integration, Pulse, dependency
  checks, and status timers.
- NotificationCenter is not disposable: it preserves actionable error and agent
  history. Its backend must remain, while permanent bell polling/presentation is
  adapted into conditional Home/activity presentation.

### Deferred loading that already works

`MaintenanceTab` stores sub-tab factories, inserts placeholders, creates the
selected sub-tab on first visit, and caches it in `_loaded_tabs`. Action Center
is one of those factories. This implementation is a protected reference pattern
and must be reused, not replaced for abstraction consistency.

### Packages and optional components

- API and daemon package boundaries remain valid and protected.
- Specialist source is still part of the base package and imported by core GUI
  startup.
- Logical component metadata and true lazy import must land before any physical
  package split is evaluated.
- A physical `loofi-fedora-tweaks-extras` RPM remains a Phase 9 go/no-go, not a
  v15 prerequisite.
- A `-devel` RPM is deferred beyond v15.

## 6. Workflow decision baseline

Counts start on the visible Home screen, use discoverable GUI controls, and
count each navigation, scope/action selection, and explicit confirmation as a
user decision. Typing and passive progress are not counted. No mutating action
was executed during Phase 0.

| Workflow | Current decisions/clicks | Baseline finding |
| --- | ---: | --- |
| Update the system | 3 | Maintenance → update scope → confirmation. There is no consolidated reviewed preview and separate outcome verification. |
| Install an application | 2 | Software → Install. The per-app path begins execution without a dedicated explicit confirmation step. |
| Diagnose a slow system | 2 to reach raw views | Performance and Processes expose raw data, but there is no guided bounded snapshot, plain-language diagnosis, or completed workflow. |
| Free disk space, direct path | 3 | Maintenance → Cleanup → action. Several direct cleanup/trim actions bypass analysis, preview, confirmation, and separate verification. |
| Free disk space, verified path | About 6–7 | Action Center adds selection, plan review, run confirmation, optional no-rollback acknowledgement, and separate verification. These safety decisions must remain. |
| Protect or recover | 2–5 per disconnected goal | Backup, Snapshots, rollback guidance, State Doctor/archive, Action Center recovery, and support export are distinct surfaces without one explanatory model. |
| Action Center lifecycle | 6–7 | Navigate/select → Review & Plan → Run → confirm → optional no-rollback acknowledgement → Verify. History remains separately inspectable. |

The Action Center count is not a simplification target. v15 may reduce competing
entry points and improve presentation, but must not remove plan review, explicit
confirmation, acknowledgement, or separate verification.

## 7. Protected v14 contracts

### Action Center — KEEP

The following remain protected architecture:

- `core/actions/contracts.py`, `catalog.py`, `orchestrator.py`, `stores.py`, and
  `center.py`.
- Canonical route `maintenance:action-center`.
- Deny-by-default executable catalog limited to `dnf-clean-all`,
  `restart-failed-service`, and `fstrim-all`.
- Expiring plans and fresh apply-time re-preflight.
- Explicit confirmation and no-rollback acknowledgement where required.
- Cross-process single-mutation lease.
- Separate verification; exit code zero alone is not success.
- Interrupted-run preservation without automatic resume, retry, or rollback.
- Manual-only behavior for all other recommendations.
- Existing CLI JSON/command contracts, authenticated read-only API, Support
  Bundle v10 evidence/redaction, settings, and history behavior.
- Home, search, and deep links may navigate or preselect only; they may not plan,
  run, verify, or mutate.

### State and observability — KEEP, UI ADAPT only

- State Doctor schemas and findings.
- State archive validation, privacy exclusions, backup, restore planning, and
  explicit restore apply behavior.
- Atomic I/O, schema/future-state handling, locks, and recovery contracts.
- Existing structured snapshot and numeric metric stores behind
  `ObservabilityService`.
- Presentation may be renamed to Repair Loofi, but persisted formats and service
  contracts remain unchanged.

### Release lineage — KEEP

- Exact release commit/tag/source/archive identity.
- 85% coverage floor.
- Fedora review and Fedora 44 install/package gates.
- RPM, Flatpak, sdist, SBOM, provenance, checksums, COPR terminal success,
  GitHub release readback, and wiki readback.

## 8. Final task classification

Every later task is classified below. Ranges are inclusive.

| Phase | KEEP | ADAPT | BUILD | DELETE | DEFER | NOT_NEEDED |
| --- | --- | --- | --- | --- | --- | --- |
| P1 | `007` | `004` | `001–003, 005–006, 008–009` | — | — | — |
| P2 | `005, 011` | `002–004, 006–008` | `001, 009–010` | — | — | — |
| P3 | `011` | `005–006, 008–009` | `001–002, 004, 010` | `003, 007` | — | — |
| P4 | `007` | `003–004, 006` | `001–002, 008` | `005` | — | — |
| P5 | — | `002, 004–006, 008` | `001, 003, 010` | `007, 009` | — | — |
| P6 | `013` | `001–004, 006, 008–011` | `005, 007, 012` | — | — | — |
| P7 | `002, 005` | `004, 006, 009` | `001, 007, 010` | `003, 008` | — | — |
| P8 | `009–010` | `001–004, 006` | `005, 007–008` | — | — | — |
| P9 | `004, 008` | `003, 007` | `001–002` | — | `005, 006A, 006B` | — |
| P10 | `009–010` | `002, 004, 006–007` | `003, 005` | — | `001, 008` | — |

There is no `NOT_NEEDED` task at Phase 0. At the Phase 9 go/no-go, exactly one
of `V15-P9-006A` and `V15-P9-006B` becomes applicable and the other becomes
`NOT_NEEDED`.

Clarifications locked by this classification:

- P1 adds destination mapping and policy around existing routes.
- P2 introduces data-only `PluginSpec` registration and true top-level lazy
  loading before P3 rebuilds the shell.
- P2 keeps Maintenance sub-tab factories and v14 regressions intact.
- P6 adapts placement and entry points but keeps Action Center as the only
  plan/run/verify UI and does not expand its catalog.
- P7 adapts notification presentation because NotificationCenter retains unique
  error/history value; it removes permanent polling rather than deleting the
  backend.
- P9 defers the physical extras decision until component/import/RPM evidence is
  available.
- P10 defers the version bump and final real-application screenshots until the
  implementation is release-ready.

## 9. Approved phase order

```text
P1 contracts and migrations
  → P2 PluginSpec, top-level lazy loading, and startup deferral
  → P3 six-destination shell
  → P4 global search
  → P5 canonical Home
  → P6 bounded workflow slices
  → P7 modes/onboarding/settings cleanup
  → P8 visual/accessibility validation and remeasurement
  → P9 packaging go/no-go
  → P10 documentation and release
```

P2 must precede P3. Building the new shell on the eager instance registry would
create an avoidable second shell/loader rewrite and would not address the
measured startup root cause.

## 10. Regression and release gates

The blocking regression set must include at least:

- Action Center: `test_action_center.py`, `test_action_center_v14.py`,
  `test_action_center_recommendations.py`, `test_api_action_center.py`, relevant
  `test_cli_health.py`, and the Action Center cases in `test_maintenance_tab.py`.
- State/observability/support: `test_state_v13.py`, `test_state_v14.py`,
  `test_observability_redaction.py`, `test_api_observability.py`, and
  `test_support_bundle_v10.py`.
- Navigation/loader: `test_navigation.py`, `test_favorites.py`,
  `test_sidebar_index.py`, `test_main_window.py`, `test_plugin_loader.py`, and
  `test_plugin_integration.py`.
- Release: `test_release_doc_check.py`, `test_build_srpm.py`,
  `test_check_fedora_review.py`, and
  `test_workflow_fedora_review_contract.py`.

Phase 0 ran a focused combined selection of 328 protected tests: 327 passed and
one navigation test failed after earlier UI tests left a conflicting
`PluginInterface` test stub in `sys.modules`. `tests/test_navigation.py` then
passed 10/10 in a clean standalone process. This is a test-order contamination
risk to address in future loader/test work, not evidence that the standalone
route manifest is invalid.

The following current checks passed:

```text
just validate-release
just check-drift
PYTHONPATH=loofi-fedora-tweaks python3 scripts/check_fedora_review.py
git diff --check
```

The full `just verify`, coverage run, package builds, CI, COPR publication, and
public readback were not rerun. Phase 0 is a read-only measurement and report
phase; those gates remain blocking for later implementation and release work.

## 11. Phase 0 exit

- Reproducible baseline: complete.
- Current HEAD and v14 tag: unambiguous.
- Startup, Home, RSS, imports, timers, threads, probes, routes, screenshots, and
  workflow decisions: recorded.
- Every P1–P10 task: classified.
- Protected v14 regressions and release gates: recorded.
- Production code and version metadata: unchanged.
- Phase 1: not started.
