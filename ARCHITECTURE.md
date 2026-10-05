# Loofi Fedora Tweaks Architecture

> Active architecture reference for released v32.1.0 "Wayfinder".
> Physical GNOME, KDE, and screen-reader qualification remains separately documented as unverified.

## Product boundary

Loofi Fedora Tweaks is a Fedora desktop utility with a PyQt6 GUI and a small
CLI. It presents curated per-user settings for GNOME and KDE alongside app
installation, updates, and diagnostics. Missing applications, schemas, or host
tools produce an unavailable state with an explanation.

The current tweak catalog contains 73 controls: 43 GNOME-only, 28 KDE-only,
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
| GNOME schemas, KDE keys, command shapes, and value validation | `loofi-fedora-tweaks/core/tweak_commands.py` |
| Set and restore actions, preflight, and independent verification | `loofi-fedora-tweaks/core/actions/tweaks.py` |
| Explicit active action allowlist | `loofi-fedora-tweaks/core/actions/catalog.py` |
| GUI rows, search, changed-only filter, reset, and restore controls | `loofi-fedora-tweaks/ui/tweaks_page.py` |
| CLI list, get, set, and restore | `loofi-fedora-tweaks/cli/commands/tweaks_commands.py` |
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

All current controls are per-user settings. They do not require administrator
authorization. KDE applications may need to be reopened before a setting is
visible in an already open window.

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
```

`just verify` runs lint, type checking, architecture rules, tests, and the
configured coverage gate. Source and RPM packaging checks do not prove the
application has been qualified in a physical GNOME or KDE session; record
those checks separately.

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
