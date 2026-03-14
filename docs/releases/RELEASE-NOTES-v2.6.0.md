# Release Notes -- v2.6.0 "API Migration Slice 2"

**Release Date:** 2026-02-25
**Codename:** API Migration Slice 2
**Theme:** Package service daemon-first migration with strict IPC compatibility and safer release pipeline gates.

## Summary

v2.6.0 extends the API migration program into package management paths.
Package actions now use daemon-first execution with robust local fallback behavior,
while IPC payload validation has been hardened to reject malformed responses safely.

## Highlights

- Package daemon handler added for install/remove/update/search/info/list/is-installed operations.
- Package services now support daemon-first execution with explicit local fallback methods.
- IPC package payload contracts validated before data is accepted.
- Focused regression tests added for daemon payload handling and fallback semantics.
- RPM build hardened against CRLF line-ending issues in mixed Windows/Linux workflows.
- CI dependency setup improved for `dbus-python` build requirements on Ubuntu runners.

## Changes

### Added

- `daemon/handlers/package_handler.py` for structured package action routing.
- IPC package payload validators in `services/ipc/types.py`.
- Release-aligned v2.6.0 workflow specs and architecture artifacts.

### Changed

- `services/package/service.py` now performs daemon-first package operations with local fallback compatibility.
- `services/ipc/daemon_client.py` now validates package payload shape before returning data.

### Fixed

- CI and release workflow reliability for dependency resolution and packaging execution.
- Linux `%prep` build failures from CRLF checkouts by normalizing copied spec line endings.

## Upgrade Notes

No intentional breaking UI or CLI interface changes.
This release focuses on migration safety, compatibility, and release pipeline stability.
