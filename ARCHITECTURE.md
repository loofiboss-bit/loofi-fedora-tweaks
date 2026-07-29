# ARCHITECTURE.md — Loofi Fedora Tweaks

> Canonical architecture reference. Agent and instruction files link here
> instead of duplicating project structure and invariants.
>
> **Current product version**: 22.0.0 "Alignment" | **Active target**: 23.0.0 "Compass" | **Python**: 3.12+ | **Framework**: PyQt6 | **Supported target**: Fedora KDE 44
>
> V20 is published on GitHub but its Fedora publication is blocked by COPR/Pulp.
> V21 and V22 are complete and public. Product metadata remains v22 while
> Compass implementation is locally qualified through the available Phase 5
> gates. Fresh Atomic and manual physical accessibility qualification remain
> open.

## Active Compass architecture

V23 composes existing trusted diagnostics into one explicit troubleshooting
journey. Its canonical authority is the
[Compass plan](docs/plans/LOOFI_FEDORA_TWEAKS_V23_PLAN.md),
[architecture contract](.workflow/specs/arch-v23.0.0.md), and
[Phase 0 baseline](docs/reports/V23_PHASE0_BASELINE.md). The
[Phase 1 report](docs/reports/V23_PHASE1_TROUBLESHOOTING_DOMAIN.md) records the
inert domain implementation, and the
[Phase 2 report](docs/reports/V23_PHASE2_EVIDENCE_COMPOSITION.md) records the
read-only composition and comparison boundary. The
[Phase 3 report](docs/reports/V23_PHASE3_TROUBLESHOOT_EXPERIENCE.md) records the
single guided route, explicit worker/service boundary, and local UI matrix. The
[Phase 4 report](docs/reports/V23_PHASE4_INTERFACES_SUPPORT.md) records the
versioned CLI, authenticated retrieval-only API, and Support Bundle v13. The
[Phase 5 report](docs/reports/V23_PHASE5_LOCAL_QUALIFICATION.md) records
exact-input local repository, CodeQL, startup, profile-budget, package, and
Traditional real-CLI/Wayland/AT-SPI evidence while keeping Atomic and manual
physical gates open.

Compass will reuse the existing `diagnostics` route, System Check, Trusted
Change Journal, observability, Action Center, and support-export boundaries. It
does not add a route, top-level destination, database, execution authority,
mutating API, background probe, or automatic repair. Phase 1 adds immutable
contracts, the closed six-profile catalog, bounded lifecycle semantics, and an
explicit future-safe JSON store. Phase 2 adds source-owned evidence adaptation,
explicit empty/partial/stale states, conservative related-change matching, and
compatible follow-up comparison. Phase 3 adds the only GUI collection entry
point through `TroubleshootingService.run()` and a lazy Qt worker adapter.
Phase 4 adds a second explicit caller through the CLI while keeping
`TroubleshootingService.run()` as the only domain collection entry point.
Constructing Home, search, navigation, the page, service, worker, or API starts
no collection.

## Runtime entry modes

All entry modes start in `loofi-fedora-tweaks/main.py`.

| Mode | Flag | Boundary |
| --- | --- | --- |
| GUI | default | `ui.main_window.MainWindow` and lazy PyQt widgets |
| CLI | `--cli` | `cli.main`; parsing and service/core calls only |
| Daemon | `--daemon` | `daemon.runtime`; D-Bus host and compatibility fallback |
| Web API | `--web` | Authenticated read-only HTTP inspection API |

The CLI never imports UI. API and daemon subpackages retain separate runtime
dependencies and require the exact base RPM EVR.

## Source layout and layer rules

```text
loofi-fedora-tweaks/
├── main.py                 # Entry-mode dispatch
├── version.py              # Version and codename authority
├── core/
│   ├── actions/            # Verified Action Center contracts and lifecycle
│   ├── home/               # PyQt-free Home composition and recommendations
│   ├── navigation/         # Destinations, routes, policy, search, migrations
│   ├── observability/      # Health metrics/snapshots and read-only status
│   ├── plugins/            # Data-only specs, discovery, registry, lazy loader
│   ├── state/              # XDG inventory, schemas, atomic I/O, backup/restore
│   ├── troubleshooting/    # Compass contracts, adapters, composition, comparison, persistence
│   └── workflows/          # Five canonical workflow contracts
├── services/               # Domain services; no PyQt imports
├── utils/                  # Shared infrastructure and compatibility shims
├── ui/                     # PyQt6 widgets and presentation only
│   └── design/             # Semantic palettes, stable geometry, QSS rendering
├── cli/                    # CLI argument parsing and service calls
├── daemon/                 # D-Bus runtime
└── api/                    # Read-only HTTP routes
```

| Layer | Allowed | Forbidden |
| --- | --- | --- |
| `ui/*_tab.py` | PyQt widgets, signals, `BaseTab`, `CommandRunner` | `subprocess`, domain policy, shell execution |
| `services/` | Domain logic and typed operations | PyQt and UI references |
| `core/` | Domain models, policy, orchestration, persistence | PyQt and UI references |
| `utils/` | Commands, runners, errors, shared infrastructure, compatibility adapters | Feature-specific UI ownership |
| `cli/main.py` | Parsing and calls into services/core/utils | UI imports |

Qt imports in `core/` or `services/` are restricted to the bridge allowlist
enforced by `tests/test_architecture_imports.py`:

- `core/workers/base_worker.py`
- `core/workers/command_worker.py`
- `core/workers/system_check_worker.py`
- `core/workers/troubleshooting_worker.py`
- `core/plugins/interface.py`
- `core/plugins/adapter.py`
- `services/security/safety.py`

## Destination and route architecture

Stable route IDs in `core/navigation/manifest.py` remain canonical.
`core/navigation/destinations.py` groups them into the v16 shell and owns
explicit, data-only presentation metadata for all 62 destination sections; it
does not replace routes or section IDs with a parallel namespace.

The unified shell contains:

| Order | Destination ID | Label | Default route |
| ---: | --- | --- | --- |
| 1 | `home` | Home | `atlas_dashboard` |
| 2 | `software_updates` | Software & Updates | `software:apps` |
| 3 | `system` | System | `system_info` |
| 4 | `network_security` | Network & Security | `network` |
| 5 | `desktop` | Desktop | `desktop` |
| 6 | `settings` | Settings | `settings` |

Specialist Tools retains the stable `advanced` destination ID. The shared
`DestinationSidebar` owns primary selection and `DestinationHost` maps the
responsive `SectionNavigator` between explicit section IDs and stable routes.
At 1180 DIP and above the primary navigation is expanded; from 900 through 1179
DIP it is a 64–72 DIP icon rail; below 900 DIP the section rail becomes a
full-width selector above content. The unified shell does not render a nested
plugin tree or an application-level horizontal route tab bar.

Specialist routes use the same shell-selected `QStackedWidget` and
`PageScaffold` contract as core routes. Local tabs are allowed only for
small same-context view sets; Community Presets is the single retained
three-view local tab group.

`NavigationPolicy` evaluates navigation mode, Fedora variant, capability,
component availability, and compatibility redirects. Missing or incomplete
specialist components fail closed with an unavailable/explanation result.
Aliases, favorites, saved last routes, direct links, and `switch_to_route()`
continue to resolve through compatibility mappings.

## Unified navigation and legacy mode compatibility

The visible Standard/Advanced selector is retired in v20. Legacy
Beginner/Intermediate/Advanced values remain accepted by idempotent migration
adapters, and the stable `advanced` destination ID is preserved. Runtime
navigation normalizes to the unified Specialist Tools surface. Visibility no
longer implies safety: confirmation, privilege, platform, and recovery rules
remain attached to each action.

## Plugin and component lifecycle

`core/plugins/spec.py` defines immutable, data-only `PluginSpec` objects for all
built-ins. A spec contains labels, route/destination metadata, module/class
names, visibility, and `core` or `specialist` component membership. Reading a
spec never imports its UI module.

Startup sequence:

1. Register specs.
2. Discover complete installed components from module files.
3. Build destination and secondary navigation from specs and policy.
4. Construct canonical Home only.
5. On route activation, `PluginLoader` imports and constructs that plugin.
6. Cache one instance and stop owned timers/threads on teardown.

The initial Home marker performs no subprocess probes or mutations and owns no
running worker thread or active timer. `scripts/benchmark_startup.py` records
milestones, RSS, imports, plugin instances, widgets, timers, threads, probes,
and installed components.

v18 keeps specialist modules in the base RPM. Static analysis found overlapping
core/specialist and CLI/API/daemon closures, so a physical extras RPM is unsafe
until a future release defines non-overlapping file ownership.

## Canonical Home

`core/home` is PyQt-free. `HomeService` reads existing persisted health, state,
history, notification, Action Center plan/run, and backup-related sources once
and returns a bounded `HomeSummary`. It does not collect new metrics or mutate
the host.

Recommendations are deterministic and prioritize state corruption,
interrupted/failed Action Center runs, pending reboot, security/health problems,
updates, stale data, and ready plans. Home may link to
`maintenance:action-center`; it never embeds its planner or executes an action.
Empty, stale, and recoverable-error states expose an explicit `Check now`
control. Only that activation lazily imports `SystemCheckWorker`, which runs the
read-only service off the UI thread and reports source, progress, elapsed time,
cancellation, and partial availability. Completed and partial runs refresh Home
by rereading persisted state; cancellation and failure preserve the previous
snapshot. Home construction still performs no collection and owns no polling
timer.
The legacy `dashboard` route redirects to System and is not a second Home.

## Global search

`core/navigation/search.py` owns the single PyQt-free search index for routes,
settings, configured migrated actions, and the three Action Center entry
points. Every result passes `NavigationPolicy`.

- `Ctrl+K`: all policy-visible results.
- `Ctrl+Shift+K`: the same model filtered to actions.
- Activation returns a route and optional preselection metadata only.
- No result carries a command vector or executable callback.

## Core workflows

`core/workflows` defines five canonical entry contracts:

- update the system;
- install an application;
- diagnose a slow system;
- analyze reclaimable disk space;
- protect the system with backup/recovery.

UI presentation may reuse existing tabs and services, but workflow decisions,
Traditional/Atomic branches, confirmations, and safe alternatives remain in
their established domain layers. `scripts/validate_v15_phase6_workflows.py`
verifies the five routes without host probes or mutations.

## Action Center invariants

`core/actions` retains the protected v14 planning boundary, the v17
reboot-aware verification contract, the v18 operation/platform metadata, and
the v19 schema-v4 optional finding context.

- `maintenance:action-center` is the only Review/Plan/Run/Verify/History UI.
- The legacy `dnf-clean-all`, `restart-failed-service`, and `fstrim-all`
  definitions remain unchanged. Assurance adds independent Fedora, Flatpak,
  firmware, application, cleanup, and recovery-point definitions.
- Plans store validated action IDs/parameters, not authoritative command vectors.
- Every definition accepts a closed parameter schema and may add stricter typed
  validation. Every plan contains exactly one action and one command vector.
- Apply regenerates commands, runs fresh preflight, enforces expiry and explicit
  confirmation, then executes through the existing privilege boundary.
- Medium-risk actions without rollback require explicit acknowledgement.
- Verification receives both the durable run and its original digest-protected
  plan. `succeeded` requires the action verifier; exit code zero is insufficient.
- Runs may enter `awaiting_reboot`; verification resumes explicitly and compares
  boot/deployment facts without automatic reboot, retry, rollback, or resume.
- One cross-process mutation lease is allowed. Interrupted runs are inspectable
  and never auto-resume.
- Home, search, API, plugins, and AI content cannot execute or expand the
  catalog. The authenticated API remains read-only.

Action plans and runs use schema v4. Writable v1-v3 state is migrated with
atomic replace, last-known-good backup, and readback. Unknown future schemas
remain read-only. Schema v4 may carry a check result ID, finding fingerprint,
evidence digest, origin route, and affected resources. This context is
non-authoritative and cannot supply an action, parameters, command, policy, or
confirmation. Context-bearing plans bind it into the plan digest; legacy plans
without context retain the v18 digest calculation.
System Check reads supported Action Center plans and runs through explicit
non-migrating store methods. Finding handoff re-resolves the latest persisted
finding, validates its evidence fingerprint, freshness, variant, and closed
mapping, and then asks Action Center to create a normal plan. System Check
findings never carry command vectors, renderers, callbacks, or execution
authority.
`core/system_check/comparison.py` reconstructs supported schema-v1 results
without rewriting the snapshot store. It compares one original check with a
later check only when profile, Fedora variant, ordering, and source availability
are compatible. Every original finding is classified as `resolved`,
`unchanged`, `worsened`, or `not_comparable`. Action Center `verified` and
finding `resolved` remain separate facts; a linked run waiting for reboot cannot
claim resolution, and a successful verifier still requires a later compatible
check collected after verification.
The canonical Support Bundle v13 preserves the bounded System Check v11 and
Trusted Change Journal v12 payloads. It can add one explicitly selected
troubleshooting session, 50 findings, 25 related changes, 25 linked plan/run
status records, and one comparison. It recursively strips or redacts paths,
hostnames, emails, secrets, network identifiers, verifier messages, commands,
and raw process output. The authenticated loopback API exposes saved System
Check and troubleshooting retrieval only; no System Check or troubleshooting
confirm, execute, plan, or collection route exists.
The HTTP route table permits mutation only for token issuance; system,
observability, profile, Action Center, and export surfaces are authenticated
GET inspection endpoints.

## State and observability

`core/state` owns XDG path inventory, schema migrations, atomic I/O, locks,
State Doctor, privacy-safe archives, restore plans, and rollback archives.
Unsupported future schemas are read-only. Writes use same-directory temporary
files, `fsync`, atomic replace, readback, private permissions, and bounded
last-known-good copies.

`core/observability` keeps numeric SQLite metrics and structured JSON health
snapshots distinct behind `ObservabilityService`. The daemon collector is
read-only and never upgrades, cleans, resets, restores, flashes firmware, or
restarts services.

`core/system_check` owns the PyQt-free, immutable System Check contracts and a
closed quick profile composed from State Doctor, Daily Maintenance, reclaim
analysis, Action Center state, and pending Atomic deployments. Each collector
has a name and timeout. Failures produce partial or failed results, cancellation
does not persist, and deterministic fingerprints use normalized redacted facts.
Completed and partial results are nested inside the existing schema-v1
`HealthSnapshot.daily_maintenance` envelope; the JSON timeline and supporting
SQLite metric store remain unchanged and v18 snapshots remain readable.

`core/system_check/presentation.py` composes those existing stores for one
read-only page and the CLI. It opens an existing metric database read-only and
does not create or migrate it. `ui/system_check_tab.py` is the only
Standard-mode System Check presentation, with Overview, Current findings, and
History views plus collapsed supporting metrics. The stable `health` route
selects Overview and `maintenance:health-timeline` selects History through the
same plugin. `ui.health_timeline_tab.HealthTimelineTab` remains an import
adapter; Action Center no longer owns a second health-history UI or Record
Snapshot action. The presentation can describe Action Center runs but cannot
plan, render, execute, or verify them.

## Commands, privilege, and Fedora variants

- Never use `sudo`; privileged GUI/CLI operations use typed `pkexec` boundaries.
- Never use `shell=True`; commands are list-based.
- Every subprocess call has a timeout.
- Always unpack `PrivilegedCommand` before execution.
- Use `SystemManager.get_package_manager()` and `SystemManager.is_atomic()`;
  never hardcode DNF behavior for Atomic Fedora.
- GUI commands run asynchronously through `BaseTab` and `CommandRunner`.
- Shared preview/execute flows use `CommandFacade`, the central executor, and
  command policy so allowlist, audit, timeout, and privilege metadata converge.

## UI conventions

- User-facing strings use `self.tr("...")`.
- Route cards expose a typed activation signal, stable route ID, keyboard
  activation, visible focus, accessible name, and accessible description.
- Standard workflows reuse shared loading, empty, unavailable, result, progress,
  and details components without replacing domain state machines.
- `ui/components/` is the single canonical presentation-only component library.
  It exposes page/content scaffolding, section presentation, cards and property
  rows, notices and states, action bars, and semantic button roles without
  importing domain services or command infrastructure.
- The shell owns `PageHeader`; `PageScaffold` owns only the bounded content
  hierarchy below it. `SectionNavigator` accepts data-only presentation items,
  emits opaque section IDs, and relies on shell policy to select rail or compact
  mode. Route and policy integration remains outside the component layer.
- `ui/layout_primitives.py` and `ui/shared_states.py` are compatibility import
  surfaces that point to the canonical components while older pages migrate.
- `ui/design/tokens.py` owns stable spacing, geometry, and typography roles.
  Themes may change semantic colors but never component geometry or hierarchy.
- `ui/design/theme_manager.py` maps system, dark, light, and high-contrast
  palettes onto one structural `assets/base.qss` source. System mode derives
  colors from `QPalette` while retaining named component selectors and the
  Qt/KDE system font.
- Runtime UI code consumes semantic color roles. Direct product colors belong
  only in the design palette source; dynamic widgets resolve roles when they
  paint so theme changes apply without reconstruction.
- Semantic icon IDs resolve through `ui/icon_pack.py`; text carries status so
  color and icons are never the only signal.

## Testing and release gates

New tests use `unittest` and `unittest.mock` style under pytest. Mock subprocess,
file, OS, and network probes; use `@patch` decorators; cover Traditional and
Atomic paths; keep tests rootless and deterministic.

Primary commands:

```bash
just test
just test-coverage
just lint
just typecheck
just verify
just validate-release
just check-packaging
just check-drift
just build-rpm
just build-flatpak
just build-sdist
```

Coverage must remain at or above 86%. Release completion additionally requires
Fedora review, Fedora 44 RPM install/upgrade, exact tag/source/artifact lineage,
checksums, SBOM, CI/COPR terminal success, GitHub asset readback, and wiki
readback.

Version changes use only:

```bash
PYTHONPATH=loofi-fedora-tweaks \
python3 scripts/bump_version.py VERSION --codename CODENAME
```

This synchronizes `version.py`, `loofi-fedora-tweaks.spec`, `pyproject.toml`,
the workflow race lock, project statistics, release notes scaffolding, and
workflow specifications. Hand-written release content and public gates remain
separate review steps.
