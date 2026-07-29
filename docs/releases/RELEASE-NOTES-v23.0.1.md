# Release Notes -- v23.0.1 "Compass"

**Release Date:** 2026-07-29

**Codename:** Compass

**Theme:** Background daemon startup hotfix

## Summary

Compass v23.0.1 fixes the packaged background daemon's systemd sandbox. The
daemon can now write its existing bounded log and health state directory while
the rest of the user's home directory remains read-only to the service.

## Highlights

- Stops the daemon's startup failure and systemd restart loop.
- Retains `ProtectHome=read-only`.
- Adds only the two existing application-owned state paths to
  `ReadWritePaths`.

## Changes

### Fixed

- Added `~/.local/share/loofi-fedora-tweaks` to the daemon unit's explicit
  writable paths. The launcher writes `startup.log` there and the daemon stores
  its bounded health timeline there.

## Safety and compatibility

- No route, schema, CLI, API, daemon protocol, dependency, or product behavior
  changes.
- Existing settings and state remain in place.
- Installation and upgrade do not enable services or apply desktop or system
  settings.
- v23.0.0 remains preserved as the exact originally published and attested
  release; this hotfix uses a new exact tag and release.

## Upgrade Notes

Upgrade all installed subpackages together. No user-data migration or manual
configuration change is required.
