# Loofi Fedora Tweaks 36.1.0 “Blueprint” — candidate

**Status:** active local candidate; this document does not claim a published
release. The existing historical `v36.0.0` tag remains untouched.

Blueprint makes **My Fedora configuration** the main new workflow. Save named
groups of desktop applications and supported user settings, move the intent as
JSON, compare it with a receiving computer, and review only the steps that are
still needed.

## My Fedora configuration

- Save several named configurations with exact RPM package identities,
  installation-scoped Flatpak refs, and an embedded existing tweak profile.
- Export `loofi.setup/v1` and inspect every app scope and setting value before
  importing it. Import writes only to the private local Loofi library.
- Compare against fresh installed-app and supported-setting observations.
  Results show presence, missing apps, scope differences, setting differences,
  unavailable items, and a read timestamp.
- Choose current local repositories/remotes and installation targets on the
  receiving computer. Source names in the file are hints; they never activate a
  repository or remote automatically. Review missing Flathub or RPM Fusion
  sources in the existing Sources flow.
- Handle work in source, application, then desktop-setting order. Applications
  reuse local AppStream discovery, per-item Action Center review and independent
  inventory verification. Settings reuse profile review and readback. Already
  satisfied items are skipped; unrelated installed apps are never removed.
- Save local step status and exact action plan/run references separately from
  portable intent. After restart, compare again before offering remaining work
  for a new review. A failed or interrupted step never triggers automatic
  continuation. Explicitly skipped items stay marked skipped, not successful.

The portable file contains no executable commands, credentials, personal home
files, system image, or previous approvals. Named Flatpak installation names
must be mapped to an installation that is confirmed on the receiving computer.
User and system installations remain separate.

The read-only CLI adds `setup list`, `setup show SETUP_ID`, and
`setup compare SETUP_ID`; each supports `--json`. It does not apply
configurations.

## Other changes

- Installed RPM details show version, architecture, package summary and license.
  A historical installation source is shown only when it can be proven.
- The app comparison view uses the same fresh reviewed RPM removal flow as the
  installed-app list and binds the request to the exact selected package.
- The tweak-profile library searches profile names and setting titles/IDs,
  preserves selection while filtering, and explains when a custom profile file
  cannot be read.

## Scope and validation

Traditional Fedora KDE with DNF5 is the first target. GNOME and Atomic keep
their existing capability boundaries. Permission management, home-directory
file migration, whole-system cloning, version locking, and unattended actions
are outside the candidate.

Candidate verification covers format round trips and safe rejection, named and
multi-installation Flatpaks, wrong desktops, missing sources, exact app review,
already-satisfied items, partial failure and restart comparison, denied
authorization, keyboard/search behavior, packaging and RPM build. The local
filter target is at most 150 ms p95. Isolated Fedora KDE and physical desktop
evidence are reported separately from automated and offscreen checks. The known
Qt accessibility crash is tracked as a separate environment limitation.

See the current [roadmap](../../ROADMAP.md), [user guide](../USER_GUIDE.md), and
[changelog](../../CHANGELOG.md), and [qualification report](../V36_QUALIFICATION.md)
for candidate scope, implementation status, and current evidence.
