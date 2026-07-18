# Architecture — v15.0.0 "Essentials"

## Goals

Make the existing Fedora control center substantially simpler and faster without
weakening v14 verified maintenance, state integrity, platform safety, or external
contracts.

## Decisions

- The default shell has exactly six destinations: Home, Software & Updates,
  System, Network & Security, Desktop, and Settings. Advanced mode adds at most
  one Advanced destination.
- Stable route and plugin IDs remain canonical. `core.navigation` owns pure
  destination placement, visibility policy, aliases, migrations, and global
  search decisions.
- `PluginSpec` is data-only. Navigation is built without importing plugin UI;
  `PluginLoader` imports and constructs one built-in only when its route opens.
- Home is a single read-only composition of existing health, state, history,
  backup, update, and Action Center stores. The legacy dashboard route redirects
  to System and does not create a second Home.
- `Ctrl+K` and `Ctrl+Shift+K` use the same policy-backed route/settings/action
  search model. Search and Home may navigate to Action Center but never create,
  apply, or verify a plan.
- Standard and Advanced are the only user-facing modes. Legacy experience-level
  values remain migration input for one release and are not a second authority.
- Built-in components are logically isolated as `core` and `specialist`.
  Component availability is derived from installed module files and fails
  closed. A physical extras RPM is deferred to v16 because file ownership and
  CLI/API/daemon dependency closures still overlap.
- The base Python runtime depends only on PyQt6. API and daemon dependencies stay
  optional and their RPM subpackages require the exact base EVR.

## Preserved v14 invariants

- `maintenance:action-center` remains the sole Review/Plan/Run/Verify/History UI.
- The executable catalog remains limited to `dnf-clean-all`,
  `restart-failed-service`, and `fstrim-all`; everything else is manual-only.
- Plans expire and are re-preflighted. Medium-risk no-rollback actions require
  acknowledgement, successful exit is not successful verification, one
  cross-process mutation lease is allowed, and interrupted runs never resume.
- Traditional Fedora uses DNF policy while Atomic Fedora uses rpm-ostree or
  manual-only guidance. All commands remain list-based, allowlisted,
  timeout-bounded, audit-linked, and separated from the `pkexec` boundary.
- State schemas, atomic writes, backups, restore planning, redaction, support
  bundles, route aliases, favorites, CLI JSON, authenticated read-only API,
  daemon, and IPC contracts remain compatible.

## Release decisions

- v15 ships logical component isolation in the base RPM; no physical
  `loofi-fedora-tweaks-extras` package is created.
- Fedora 44 remains the supported target and Fedora 45 remains preview/advisory.
- Release artifacts must be built from one exact commit. The historical
  `v15.0.0` Nebula tag object is preserved as `legacy-v15.0.0-nebula`; the
  canonical tag must peel to the exact Essentials release commit.
