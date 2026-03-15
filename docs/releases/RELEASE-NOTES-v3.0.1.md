# Release Notes -- v3.0.1 "Aegis"

**Release Date:** 2026-03-15  
**Codename:** Aegis  
**Theme:** Post-release API hardening and settings polish

## Summary

v3.0.1 is a patch release for the Aegis line. It tightens desktop API defaults after the initial v3.0.0 release by hiding default FastAPI docs/OpenAPI surfaces, failing closed on unsafe CORS overrides, extending Safe Mode protection to profile mutation routes, and exposing the plugin auto-update safety toggle directly in Settings.

## Highlights

- FastAPI docs, ReDoc, and OpenAPI discovery disabled by default
- Unsafe `LOOFI_CORS_ORIGINS` values ignored unless API exposure is explicitly allowed
- Profile apply/import routes now block under Safe Mode and audit both blocked and successful mutations
- `plugin_auto_update` now appears in **Settings → Advanced** and survives reset correctly
- `.pytest-tmp/` ignored so Windows-local test validation does not dirty the git tree

## Changes

### Added

- Regression coverage for hidden API docs/OpenAPI endpoints and loopback-safe CORS handling
- Regression coverage for profile Safe Mode mutation guards and plugin auto-update reset behavior

### Changed

- Runtime/package metadata and user-facing docs now advertise `3.0.1` while keeping the `Aegis` codename
- README and release-note indexes now point to the current patch release instead of the original v3.0.0 landing page

### Fixed

- Default desktop API behavior no longer exposes FastAPI discovery endpoints after the initial 3.0.0 release
- Profile mutation endpoints now honor the same Safe Mode write protections as executor routes
- Repo-local Windows pytest temp directories no longer pollute release branches during validation

## Validation

- Focused API/settings regressions: 66 passed
- Related auth/settings/daemon regressions: 94 passed
- Full test suite: 7246 passed, 125 skipped

## Upgrade Notes

- No manual migration is required from `v3.0.0`
- If you intentionally expose the Web API to other hosts, review your `LOOFI_CORS_ORIGINS` values because unsafe remote origins are now ignored by default
- Existing `plugin_auto_update` values are preserved; the setting is now visible in **Settings → Advanced**
