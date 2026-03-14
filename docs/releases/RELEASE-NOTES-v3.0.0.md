# Release Notes -- v3.0.0 "Aegis"

**Release Date:** 2026-03-14  
**Codename:** Aegis  
**Theme:** API exposure control, Safe Mode defaults, plugin update safety, and version consistency cleanup

## Summary

v3.0.0 hardens the local automation surface and makes the safety defaults explicit. The Web API now fails closed on unsafe non-loopback binds unless `--unsafe-expose` is provided, auth bootstrap storage is validated more strictly, and route-aware throttling now separates bootstrap, read-only, and mutating traffic. Safe Mode is enabled by default for API mutations, and daemon-driven plugin updates remain opt-in with verification and rollback protections preserved. This release also aligns runtime and packaging metadata under the `3.0.0` / `Aegis` version line.

## Highlights

- Loopback-only Web API startup unless `--unsafe-expose` is explicitly provided
- Owner-only API auth storage validation with fail-closed bootstrap behavior
- Route-aware throttling for auth, read, and mutation API buckets with retry guidance
- Safe Mode enabled by default for mutating API execution
- Shared confirmation dialogs now show risk badges and revert hints from the registry
- `plugin_auto_update` is a first-class persisted setting and defaults to off
- Daemon plugin updates preserve checksum verification and rollback behavior when enabled
- Canonical version metadata aligned to `3.0.0` / `Aegis`

## Changes

### Added

- Safe Mode setting exposure in the Settings behavior panel
- Focused regression coverage for Safe Mode, daemon update safety, and API trust-boundary hardening
- Registry-backed risk and revert context in confirmation dialogs

### Changed

- Web API bind validation now refuses non-loopback hosts unless the caller opts in with `--unsafe-expose`
- API rate limiting now distinguishes bootstrap/auth, read-only, and mutation traffic
- Daemon plugin update checks now prefer explicit settings values over legacy config fallback

### Fixed

- Silent API trust-boundary expansion when non-loopback binds were requested without explicit intent
- Invalid or unsafe persisted auth storage handling during bootstrap/token issuance
- Version drift between `version.py`, `pyproject.toml`, and `loofi-fedora-tweaks.spec`

## Validation

- Focused TASK-007 verification: plugin auto-update settings, daemon safety, and installer rollback checks passed
- Focused TASK-008 verification: API loopback/auth/rate-limit regressions passed
- Focused TASK-009 verification: Safe Mode, settings, confirmation dialog, and daemon regressions passed
- Focused TASK-010 verification: version alignment checks passed

## Upgrade Notes

- If you intentionally expose the Web API on a LAN, you must now pass `--unsafe-expose`; `LOOFI_API_HOST=0.0.0.0` alone is no longer enough
- Existing legacy `plugin_auto_update` config values still migrate forward, but Settings is now the canonical control surface
- Safe Mode starts enabled for mutating API actions; disable it explicitly in **Settings → Behavior** if your workflow requires remote write actions

