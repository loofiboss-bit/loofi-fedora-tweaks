# Architecture — v31.1.0 "Mastery"

## Authority and Retained Boundary

The approved baseline is v30.2.1 at commit `f4a71a9`. Delivery covers local
implementation, regression coverage, automated qualification, and release documentation.
The release identity is assigned to v31.1.0 to resolve the historical tag collision with
the archived 2026-02-13 Smart UX tags.

Retain Home, Apps, Tweaks, Health, and Updates navigation tabs. The CLI surface
now natively includes `tweaks` and `apps` domain commands alongside the existing
eight domains (`info`, `check`, `updates`, `troubleshoot`, `changes`, `activity`,
`doctor`, `support-bundle`), achieving complete CLI and GUI parity.
The tweak catalog is expanded from 14 to 22 verified controls across GNOME, KDE,
and system packaging (DNF5 parallel downloads).
Action Center remains the sole mutation authority with schema-v4 plans and runs.
Fail-closed policy verification and Polkit boundaries are strictly preserved.

## Architectural Changes & Enhancements

1. **Expanded Tweak Catalog & Schema Routing**:
   - GNOME schema routing: Dynamically associates tweak IDs with exact GSettings
     schemas (`org.gnome.desktop.wm.preferences`, `org.gnome.desktop.peripherals.touchpad`,
     `org.gnome.settings-daemon.plugins.color`, `org.gnome.desktop.sound`, `org.gnome.desktop.interface`).
   - KDE configuration mapping: Integrates `kcminputrc` (Touchpad tap-to-click)
     and `kwinrc` (NightColor) into the declarative `kreadconfig6`/`kwriteconfig6` pipeline.
   - Privileged System Tweaks: Introduced `dnf-parallel-downloads` with Polkit
     elevation (`pkexec`) and confirmation policy, while remaining unavailable
     on Atomic Fedora deployments.
   - Command Policy & Execution: Allowed read-only configuration dumping
     (`--dump-main-config`) in execution policy.

2. **CLI Parity**:
   - Added `tweaks` command domain with `list`, `get`, `set`, and `restore` subcommands,
     supporting human-readable tabular output and machine-readable JSON (`--json`).
   - Added `apps` command domain with `list` and `install` subcommands,
     supporting `--dry-run` and structured JSON output.

3. **Dynamic Package Manager Resolution**:
   - Catalog clean-all commands dynamically resolve `runtime.package_manager()`
     instead of hardcoding `dnf5`, ensuring correctness across Fedora packaging environments.

4. **Curated Applications Catalog**:
   - Added Flatseal, Mission Center, Spotify, and Neovim to the curated catalog.

5. **UI Search & Layout**:
   - `TweaksPage` dynamically toggles category card visibility during search filtering
     so that cards with no matching rows are cleanly hidden.

## Qualification and Verification

- Line coverage gate >= 85% enforced across the test suite.
- Exact CLI parser contract regression digest maintained.
- Full verification through `just verify` and automated documentation validation.
