# ARCHITECTURE.md — Loofi Fedora Tweaks

> Canonical architecture reference for the v28.0.2 "Ease" release candidate.
> The supported product
> is a desktop-neutral Fedora application built with Python 3.12+ and PyQt6.

This document describes the active product boundary.  Historical release notes
may mention retired implementation details, but they are not supported runtime
or packaging contracts.

## Product boundary

Loofi Fedora Tweaks is a focused Fedora maintenance application.  It combines
read-only inspection, capability-aware guidance, and reviewed persistent
changes in one small GUI and a matching CLI.  The application remains useful
when optional host tools are missing: each source reports an explicit
`available`, `unavailable`, `stale`, or `error` state instead of pretending
that a different Fedora setup was detected.

The Ease release candidate preserves the intentionally small Core boundary:

- five primary destinations: Home, Updates & Apps, System Health, Protection &
  Recovery, and Changes;
- an immutable `PlatformProfile` for Fedora version, architecture, desktop,
  session, capabilities, and deployment backend;
- one Action Center authority for every persistent host mutation;
- GUI and CLI as the only runtime entry modes;
- a COPR-backed RPM as the supported distribution artifact.

The product does not ship a background service, local web API, D-Bus
runtime, Flatpak application bundle, specialist suite, marketplace, unattended
scheduler, automatic retry, automatic rollback, or automatic reboot.

The authoritative v28 contract is [.workflow/specs/arch-v28.0.2.md](.workflow/specs/arch-v28.0.2.md).
The previous public release record is [V28_RELEASE_PUBLICATION.md](docs/reports/V28_RELEASE_PUBLICATION.md).
The v28.0.2 publication record is added after the canonical release workflow
completes.

## Runtime entry modes

All launches begin in `loofi-fedora-tweaks/main.py`.

| Mode | Invocation | Boundary |
| --- | --- | --- |
| GUI | `loofi-fedora-tweaks` | `ui.main_window.MainWindow` and lazy PyQt widgets |
| CLI | `loofi-fedora-tweaks --cli ...` | `cli.main`, parser domains, and domain services |

The CLI never imports UI modules.  GUI views never execute subprocesses or
import mutation services directly; they hand reviewed intent to the domain
layer and receive typed state/results back.

## Five destinations and routing

`core/product_catalog_records.py` is the data authority for route, plugin,
section, destination, capability, variant, risk, and handoff metadata.
`core/product_catalog.py` composes immutable records, while
`core/navigation/manifest.py` and `core/navigation/destinations.py` expose
compatibility projections for existing consumers.  No second catalog may
declare competing product metadata.

| Order | Destination ID | Label | Default route |
| ---: | --- | --- | --- |
| 1 | `home` | Home | `atlas_dashboard` |
| 2 | `software_updates` | Updates & Apps | `software:apps` |
| 3 | `system` | System Health | `system_info` |
| 4 | `network_security` | Protection & Recovery | `network` |
| 5 | `changes` | Changes | `changes` |

Settings remains a header-level route (`settings`) rather than a sixth primary
destination.  Stable route IDs and compatibility redirects are preserved for
existing saved links.  `NavigationPolicy` evaluates route, Fedora variant,
capability, component availability, and explicit compatibility mappings;
missing or incomplete features return a typed unavailable explanation.

The shell owns primary selection and responsive layout.  At wide sizes the
navigation is expanded; at medium sizes it becomes an icon rail; at narrow
sizes it becomes a full-width selector.  The navigation component emits opaque
route/section IDs and has no command or callback authority.

## Source layout and layer rules

```text
loofi-fedora-tweaks/
├── main.py                 # GUI/CLI dispatch only
├── version.py              # Version and codename authority
├── core/
│   ├── actions/            # Plans, policy, execution, verification, leases
│   ├── catalog_records/    # Immutable product catalog data
│   ├── change_journal/     # Trusted local change records and presentation
│   ├── diagnostics/        # Health and Fedora readiness contracts
│   ├── export/             # Redacted support and migration exports
│   ├── home/               # PyQt-free Home composition
│   ├── navigation/         # Routes, destinations, policy, search, migration
│   ├── observability/      # Read-only metrics, snapshots, and timelines
│   ├── platform/           # Immutable platform profile and capabilities
│   ├── state/              # XDG inventory, schemas, atomic I/O, backups
│   ├── system_check/       # Bounded checks, findings, comparisons, handoff
│   ├── troubleshooting/    # Bounded profiles and saved evidence
│   └── workflows/          # Canonical workflow contracts
├── services/               # PyQt-free typed domain services
├── cli/                    # Public parser and command handlers
├── ui/                     # PyQt6 presentation and workers
├── utils/                  # Shared command, storage, and compatibility helpers
├── config/                 # Data-only application catalog/configuration
└── resources/              # Translations and packaged resources
```

| Layer | Owns | Must not own |
| --- | --- | --- |
| `core/` | Contracts, policy, orchestration, persistence, typed state | PyQt widgets or direct host mutation from presentation paths |
| `services/` | Bounded domain collection and operation adapters | UI imports, shell strings, or hidden background work |
| `ui/` | Presentation, signals, accessibility, lazy worker adapters | `subprocess`, command vectors, or policy decisions |
| `cli/` | Argument parsing, serialization, and calls into domains | UI imports or arbitrary command execution |
| `utils/` | Shared infrastructure and compatibility adapters | New feature-specific authority |

The only approved Qt bridges in `core/` and `services/` are the existing worker
or safety adapters.  Architecture tests enforce the allowlist and reject new
presentation-to-host shortcuts.

## Platform and capability model

`core/platform/profile.py` defines the immutable `PlatformProfile`.  Detection
is explicit for Fedora release, CPU architecture, desktop/session, and
deployment backend (`dnf5`, `rpm_ostree`, `bootc`, or `unknown`).
`core/platform/capabilities.py` derives the optional host-tool capabilities
used by navigation, readiness, update sources, and Action Center eligibility.

Unknown values fail closed.  In particular, unknown deployment must not be
treated as traditional Fedora, unknown desktop must not select KDE-specific
behavior, and unknown reboot state must not be reported as safe to continue.
Traditional, Atomic, and bootc branches remain separate in the domain layer;
they are never inferred from a UI label.

## Home and read-only inspection

`core/home` reads existing persisted health, state, history, plans, runs, and
backup metadata and returns a bounded `HomeSummary`.  Constructing Home does
not probe the host, start a polling timer, or mutate state.  A visible `Check
now` activation is the only entry point that starts the read-only System Check
worker.  Completed, partial, cancelled, and failed results retain explicit
source/progress/error state and refresh Home by rereading persisted data.

System Health composes System Check, troubleshooting, storage, hardware, and
support export.  Troubleshooting sessions use a closed profile catalog,
bounded collection, immutable findings, and redacted persistence.  Inspection
is advisory and does not create a mutation plan implicitly.

## Action Center mutation boundary

`core/actions` is the sole authority for persistent host changes.  Every
change follows this lifecycle:

```text
inspect → select → review plan → authorize → execute → verify
```

Plans contain a closed action ID and typed parameters, never a command vector
supplied by the user, UI, document, or external source.  Before execution the
orchestrator performs fresh preflight, validates the platform/backend and
capabilities, checks expiry, obtains the mutation lease, and requires explicit
confirmation for actions that need it.  The executor reconstructs the
allowlisted command from the action definition.

Verification is an independent step.  A zero exit code is not a successful
maintenance result by itself.  Runs can remain `awaiting_reboot`, but the app
never reboots, retries, rolls back, or resumes them automatically.  The user
must explicitly run verification after the relevant host event.  Interrupted,
failed, and verification-failed runs remain inspectable in Changes.

The five visible facts in Changes are: change, risk, authorization,
verification, and rollback/recovery guidance.  Activity history is source-owned
evidence and does not imply that a generic Undo operation is available.

## Updates and native application handoff

Updates & Apps keeps system packages, Flatpak applications, and firmware as
independent sources.  Each follows `Check → Select source → Review changes →
Run → Verify`; a missing binary or unsupported backend is shown as unavailable
with a safe next step.  Flatpak remains an optional host update source, not a
distribution format for this application.

Application discovery is handed to the installed desktop software center via
AppStream/XDG metadata when available.  Loofi does not maintain a second app
store or silently choose a desktop-specific installer.

## State, observability, and support

`core/state` owns XDG paths, versioned schemas, migrations, locks, backups,
atomic replacement, readback, and State Doctor.  Writes use same-directory
temporary files, `fsync`, private permissions, bounded last-known-good copies,
and explicit future-schema read-only behavior.  User state is preserved across
package upgrades and uninstall.

`core/observability` reads metrics and structured health snapshots without
creating hidden collectors.  `core/change_journal` records bounded local
source evidence for package, firmware, Flatpak, Action Center, and application
activity.  Support bundles recursively redact paths, hostnames, emails,
secrets, network identifiers, commands, and raw process output before export.

## Commands, privilege, and safety

- Never use `sudo`; privileged commands use the desktop's standard `pkexec`
  authorization agent.
- The RPM ships no project-specific polkit action files.  Authorization is not
  granted by browsing, previewing, or reading a document.
- Never use `shell=True`; subprocess calls are explicit list arguments with
  bounded timeouts.
- Always validate a `PrivilegedCommand` through the command policy before
  execution and write audit evidence for the reviewed run.
- Never execute an arbitrary command entered in the CLI, UI, or an imported
  file.
- Missing tools, unknown platforms, unsupported capabilities, stale plans, and
  unverifiable outcomes fail closed with user-facing guidance.

## CLI contract

The public CLI intentionally mirrors the eight canonical domains:

```text
info
check
updates
troubleshoot
changes
activity
doctor
support-bundle
```

`--json`, `--timeout`, and `--dry-run` are global inspection/planning controls.
The CLI may inspect and create a reviewed plan, but only `changes apply` with
explicit confirmation may execute an existing plan or named Action Center
definition.  `changes verify` remains a separate explicit command.

## Packaging and distribution

The supported production package is one complete RPM built from
`loofi-fedora-tweaks.spec` and published through the Loofi COPR project.  The
base package owns the complete application tree; no API, daemon, or extras
subpackage exists.  `requirements.txt` is generated from the runtime project
dependencies and contains no retired service stack.

Release CI builds and tests the RPM and source distribution.  It does not
install SDKs or publish a Flatpak artifact.  `install.sh` is a guarded,
auditable convenience wrapper around COPR and `uninstall.sh` removes only the
package/repository paths it names while preserving user state.

## Testing and release gates

Use the repository command surface:

```bash
just test
just test-coverage
just lint
just typecheck
just verify
just check-packaging
just validate-release
just check-drift
just build-rpm
just build-sdist
```

Tests mock process, file, OS, and network probes; cover Traditional and Atomic
branches; and remain rootless and deterministic.  `scripts/validate_architecture.py`
checks import boundaries, annotation/function budgets, catalog authority, and
the System Check domain.  `scripts/analyze_component_boundaries.py` records
component reachability and verifies that the RPM has no retired subpackages or
custom polkit action installation.

Local/offscreen evidence does not prove physical desktop accessibility,
authorization-agent behavior, reboot completion, or Atomic installation.  For
v28.0.2 these gates are intentionally recorded as unverified under the
authorized manual-test skip; they must not be inferred from rootless tests.
The maintained coverage gate remains 85% (87% repository-wide measured locally
for this release); the plan's repository-wide 90% target remains open.

## Versioning

Use the version helper for synchronized changes:

```bash
PYTHONPATH=loofi-fedora-tweaks \
python3 scripts/bump_version.py VERSION --codename CODENAME
```

This updates the version authority, spec, project metadata, race lock,
statistics, and release-note scaffolding.  Release publication and external
readback remain explicit, separately authorized steps.
