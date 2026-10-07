# Loofi Fedora Tweaks Architecture

> Active architecture reference for v32.3.0 "Clarity".
> Physical GNOME, KDE, and screen-reader qualification remains separately documented as unverified.

## Product boundary

Loofi Fedora Tweaks is a Fedora desktop utility with a PyQt6 GUI and a small
CLI. Overview is the default GUI route. Its read-only dashboard and System Monitor
share a window-owned asynchronous collector. It presents curated per-user settings for GNOME and KDE, plus one
system-wide DNF setting, alongside app installation, updates, and diagnostics.
Missing applications, schemas, or host tools produce an unavailable state
with an explanation.

The current tweak catalog contains 76 controls: 46 GNOME-only, 28 KDE-only,
and two shared controls. The GUI and CLI project the controls supported by the
detected Fedora desktop and deployment backend.

The product has no background service, local web API, remote-control endpoint,
unattended scheduler, automatic retry, automatic rollback, or automatic reboot.
The supported distribution package is one RPM built from
`loofi-fedora-tweaks.spec`.

## Source of truth

| Concern | Active source |
| --- | --- |
| Tweak IDs, labels, choices, and desktop scope | `loofi-fedora-tweaks/core/tasks/tweaks.py` |
| Built-in reviewed desktop presets | `loofi-fedora-tweaks/core/tasks/tweak_presets.py` |
| GNOME schemas, KDE keys, command shapes, and value validation | `loofi-fedora-tweaks/core/tweak_commands.py` |
| Set and restore actions, preflight, and independent verification | `loofi-fedora-tweaks/core/actions/tweaks.py` |
| Explicit active action allowlist | `loofi-fedora-tweaks/core/actions/catalog.py` |
| GUI rows, search, one-setting inspection, reset, and restore controls | `loofi-fedora-tweaks/ui/tweaks_page.py` |
| CLI list, get, set, restore, and presets | `loofi-fedora-tweaks/cli/commands/tweaks_commands.py` |
| Generated catalog reference | `docs/TWEAKS.md`, from `scripts/gen_tweaks_doc.py` |

Add a setting to the declarative catalog and its closed command metadata. The
UI, CLI, action definitions, and catalog documentation consume these sources;
they must not introduce a second setting registry.

## Change and restore boundary

`core/actions` is the only authority for persistent host changes. A tweak
change follows this lifecycle:

```text
inspect → prepare exact setting → authorize when required → execute → verify
```

The action catalog accepts typed setting values and reconstructs allowlisted
command vectors. UI code does not execute host commands. The CLI uses the same
Action Center and does not accept arbitrary command text.

Every setting is read before planning and independently read again after a
change. A successful exit code without matching readback is a failed change.
The action history stores the verified previous and resulting values inside
the existing schema-v4 run record; no migration is needed for catalog-only
settings. Restore accepts a verified `source_run_id`, checks that the setting
has not drifted or been superseded, and records a separate verified action.
There is no generic undo, bulk restore, or automatic rollback.

GNOME and KDE settings are per-user and do not require administrator
authorization. The DNF parallel-download setting is system-wide and requires
administrator authorization. Reset uses Loofi's curated standard value; it
does not query the active desktop schema's current default. KDE applications
may need to be reopened before a setting is visible in an already open window.

## Desktop-specific settings

- GNOME settings use exact `gsettings` schema and key pairs. GNOME Files
  controls use `org.gnome.nautilus.preferences`; when that schema is not
  installed, the setting is unavailable.
- KDE settings use closed `kreadconfig6` and `kwriteconfig6` vectors. The
  Dolphin path control is unavailable when the `dolphin` executable is absent.
- KWin borderless maximized windows use the `Windows` group in `kwinrc` and
  default to false.
- Fedora desktop and deployment detection comes from the immutable
  `PlatformProfile`. Unknown or unsupported profiles fail closed.

## Runtime layers

| Layer | Owns | Must not own |
| --- | --- | --- |
| `core/` | Contracts, policy, action orchestration, state, command metadata | Qt widgets or host changes from presentation paths |
| `services/` | Bounded domain adapters and platform services | UI imports, shell strings, or hidden background work |
| `ui/` | Presentation, signals, accessibility, workers | Subprocesses, command vectors, or mutation policy |
| `cli/` | Argument parsing, serialization, and domain calls | UI imports or arbitrary command execution |
| `utils/` | Shared infrastructure and compatibility adapters | New feature-specific authority |

All launches begin in `loofi-fedora-tweaks/main.py`. GUI widgets request
domain work through existing controllers and workers. CLI `tweaks list`,
`get`, `set`, and `restore` project the same catalog and actions as the GUI.

## State and packaging

`core/state` owns application state under the user's XDG directories. Reads
and writes preserve the existing versioned plan and run formats, use bounded
atomic persistence, and keep corrupt or future data read-only. Uninstalling
the RPM preserves user state.

The repository command surface is the maintained verification interface:

```bash
just verify
just build-rpm
just check-packaging
python3 scripts/gen_tweaks_doc.py --check
python3 scripts/bump_version.py --check
```

`just verify` runs lint, type checking, architecture rules, catalog and version
consistency checks, tests, and the configured coverage gate. Source and RPM
packaging checks do not prove the application has been qualified in a physical
GNOME or KDE session; record those checks separately.

## Wayfinder presentation and session activation

The catalog provides control kind, search terms, and application guidance.
Tweaks combines an exclusive view, category, and text filter. Favorites are
unique stable IDs in `favorite_tweaks` through SettingsManager; failed saves
restore the prior visible favorite state. Editors distinguish the last verified
value from a pending request and block mutations during active execution.

KWin setting writes retain the established saved-value verification and
source-bound restoration contracts. `core/actions/tweak_operations.py` is the
shared GUI worker/CLI adapter for a separate `activate-kwin-tweak` action.
Only the fixed KWin reconfigure call is allowed; supportInformation must match
the requested runtime value. Failed activation is a session warning, preserves
the saved change and restoration offer, and never restarts KWin or rolls back.

## Control center presentation

`overview` is a canonical built-in route and plugin in the product catalog.
Older Atlas links continue to open Tweaks; persisted valid last-route and theme
preferences are preserved. Tools is a disclosure of the five maintained tool
groups, not an additional route authority.

`services/system/dashboard.py` owns Qt-free snapshots with source, units,
timestamp, and availability for each reading. It reuses PerformanceCollector
and TemperatureManager and reads saved update, health, and action observations
without starting maintenance checks. Missing or malformed readings cannot
become healthy zeroes. GPU queries are read-only, bounded, and limited to
active devices. No optional tools or drivers are installed.

The window owns DashboardController. Overview and Monitor consume its immutable
snapshots; the worker never collects on the UI thread. Fast readings refresh
every two seconds, sensors every five, only while a consumer is visible.
Hiding or minimizing suspends collection; resuming resets differential
baselines. Shutdown joins pending work before Qt objects are destroyed.

DESIGN.md is the presentation contract. ThemeManager selects the Loofi light
or dark palette in system mode and retains explicit themes and high contrast.
All maintained pages share semantic colors, system typography, controls, and
feedback, without adding a second action execution boundary.

## Everyday workflow extensions

`core/tasks/tweak_profiles.py` defines strict portable profiles, immutable reviews,
and sequential results. Review does not allocate persisted plans; each selected
entry is prepared and revalidated just before Action Center execution.
`core/tasks/tweak_presets.py` maps the closed Reduced motion and File navigation
presets into those same profile reviews. `core/tasks/tweaks.py::inspect_one` reads
one selected setting and its restore offer within an eight-second shared budget;
the owning window routes this through its existing operation worker.
`services/software/update_recovery.py` hydrates saved observations and durable run
identities without executing updates. `core/tasks/next_steps.py` projects recorded
dashboard observations into at most three navigation suggestions.

Global settings search projects the current desktop's canonical tweak records
into navigation results; it does not snapshot or write system settings.
`ActivityJournalWorker` loads the latest 25 local Loofi runs on first visit and
resolves a requested run ID through the journal source's exact lookup, independent
of that recent-page limit. External history remains explicitly refreshed.

Application preferences use state schema 3. The one-time migration disables the
previous startup release-check flag, while a later explicit opt-in is preserved.
The check starts asynchronously after the first GUI frame, has a four-second
network timeout, reads only the Loofi release version, and does not download or
install updates. Loofi notifications respect the saved notification preference;
start-minimized is honored only with a visible system tray. Logging preferences
update the existing Loofi logger and handlers only after settings save succeeds.

Installed applications use source, installation, and full ref as identity.
`core/actions/installed_applications.py` owns reviewed Flatpak removal and independent
inventory verification. `services/hardware/diagnostic_probes.py` implements bounded,
read-only sound/Bluetooth observations with unknown states and cancellation.
Flatpak metadata permissions are read for one inventory-verified ref and installation.
The parser retains category, key, and value; UI and JSON output redact environment
values and identify the result as metadata rather than effective access.
Window-owned operation workers and installed-page samplers participate in deferred
shutdown; no worker is destroyed while running. Existing plan/run schemas remain
unchanged. Portable profiles do not reactivate retired profile stacks.
