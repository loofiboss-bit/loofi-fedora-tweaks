# ARCHITECTURE.md — Loofi Fedora Tweaks

> Canonical architecture reference. Agent and instruction files link here
> instead of duplicating project structure and invariants.
>
> **Version**: 15.0.0 "Essentials" | **Python**: 3.12+ | **Framework**: PyQt6 | **Supported target**: Fedora KDE 44

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
- `core/plugins/interface.py`
- `core/plugins/adapter.py`
- `services/security/safety.py`

## Destination and route architecture

Stable route IDs in `core/navigation/manifest.py` remain canonical.
`core/navigation/destinations.py` groups them into the v15 shell; it does not
replace them with a parallel namespace.

Standard mode contains exactly:

| Order | Destination ID | Label | Default route |
| ---: | --- | --- | --- |
| 1 | `home` | Home | `atlas_dashboard` |
| 2 | `software_updates` | Software & Updates | `software:apps` |
| 3 | `system` | System | `system_info` |
| 4 | `network_security` | Network & Security | `network` |
| 5 | `desktop` | Desktop | `desktop` |
| 6 | `settings` | Settings | `settings` |

Advanced mode adds one `advanced` destination. The shared
`DestinationSidebar` owns primary selection and `DestinationHost` owns secondary
route selection. Standard mode does not render a nested plugin tree.

`NavigationPolicy` evaluates navigation mode, Fedora variant, capability,
component availability, and compatibility redirects. Missing or incomplete
specialist components fail closed with an unavailable/explanation result.
Aliases, favorites, saved last routes, direct links, and `switch_to_route()`
continue to resolve through compatibility mappings.

## Standard and Advanced modes

`utils/navigation_mode.py` is the sole post-migration settings authority:

```text
navigation_mode = standard | advanced
```

Legacy Beginner/Intermediate/Advanced values are accepted only by idempotent
migration adapters. Standard is the default. Advanced reveals policy-approved
specialist routes but never changes confirmation, privilege, or execution
rules. Returning to Standard preserves hidden settings and pins.

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

v15 keeps specialist modules in the base RPM. Static analysis found overlapping
core/specialist and CLI/API/daemon closures, so a physical extras RPM is unsafe
until v16 defines non-overlapping file ownership.

## Canonical Home

`core/home` is PyQt-free. `HomeService` reads existing persisted health, state,
history, notification, Action Center plan/run, and backup-related sources once
and returns a bounded `HomeSummary`. It does not collect new metrics or mutate
the host.

Recommendations are deterministic and prioritize state corruption,
interrupted/failed Action Center runs, pending reboot, security/health problems,
updates, stale data, and ready plans. Home may link to
`maintenance:action-center`; it never embeds its planner or executes an action.
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

`core/actions` remains protected v14 architecture. v15 changes placement and
presentation only.

- `maintenance:action-center` is the only Review/Plan/Run/Verify/History UI.
- The executable catalog remains `dnf-clean-all`,
  `restart-failed-service`, and `fstrim-all`.
- Plans store validated action IDs/parameters, not authoritative command vectors.
- Apply regenerates commands, runs fresh preflight, enforces expiry and explicit
  confirmation, then executes through the existing privilege boundary.
- Medium-risk actions without rollback require explicit acknowledgement.
- `succeeded` requires the action verifier; exit code zero is insufficient.
- One cross-process mutation lease is allowed. Interrupted runs are inspectable
  and never auto-resume.
- Home, search, API, plugins, and AI content cannot execute or expand the
  catalog. The authenticated API remains read-only.

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

Coverage must remain at or above 85%. Release completion additionally requires
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
