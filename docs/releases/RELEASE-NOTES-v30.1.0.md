# Release Notes — v30.1.0 "Personalize" Local Candidate

**Candidate date:** 2026-09-24<br>
**Status:** Not published or installed.

## Summary

Loofi Fedora Tweaks now leads with Home, Apps, Tweaks, Health, and Updates.
Tweaks reads the current host value before offering a change and reports a
saved result only after an independent readback. Health collects symptom-led
diagnostics and everyday storage maintenance.

## Changes

- Added five GNOME controls, two KDE controls, and available power profiles.
- Kept custom KDE settings visible and left them unchanged until selected.
- Moved storage trim and package cache cleanup from Tune profiles to Health.
- Kept old route links, CLI commands, action IDs, and saved Activity readable.
- Kept Action Center as the internal execution authority; normal reviews now
  complete on the originating page or Health.

## Qualification

`LOOFI_IPC_MODE=disabled QT_QPA_PLATFORM=offscreen just verify` passed with
4,931 tests passed, 40 skipped, 852 subtests passed, and 85.96% line coverage.
After the final maintenance-link focus change, 13 focused tweak and Health
tests passed. `just stats-check`, `just validate-release`, `just check-packaging`,
and `git diff --check` passed. Offscreen Home and Tweaks captures were reviewed
in light and dark themes at 100% and 200% Qt scaling; keyboard search and
refresh navigation passed an automated test. Read-only KDE values were also
observed on the active host, without applying a change.

Physical GNOME, KDE interaction, Polkit, Atomic, screen-reader, and manual
keyboard and scaling checks remain `unverified`; offscreen checks do not
establish these results.

## Upgrade notes

No persisted-state migration is required. This candidate does not authorize
publication, installation, or changes to the current desktop session.
