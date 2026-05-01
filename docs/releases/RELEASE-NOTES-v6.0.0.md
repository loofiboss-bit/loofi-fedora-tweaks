# Release Notes -- v6.0.0 "Compass"

**Release Date:** 2026-05-01  
**Codename:** Compass  
**Theme:** Guided release readiness without automatic repair

## Summary

v6.0.0 "Compass" turns the v5 Fedora KDE 44 readiness center into a generic release readiness workflow. Fedora KDE 44 remains the supported target, and Fedora 45 is exposed only as a preview profile for planning.

## Highlights

- Generic `release_readiness` engine with target metadata.
- Fedora 45 preview profile with advisory status and release milestone metadata.
- Typed recommendations for readiness findings: command preview, risk, reversibility, rollback hint, docs, and manual-only flags.
- Grouped readiness dialog with severity filters, beginner/advanced detail, async probes, copy support summary, and support bundle export.
- New CLI command: `loofi-fedora-tweaks --cli readiness [--target 44|45-preview] [--advanced]`.
- Support Bundle v4 with generic readiness payloads and v3 field aliases.

## Changes

### Added

- `core/diagnostics/release_readiness.py`
- `core/export/support_bundle_v4.py`
- `ui/release_readiness_dialog.py`
- v6 workflow specs in `.workflow/specs/`
- Unit coverage for target metadata, Fedora 45 preview behavior, CLI output, support bundle v4 aliases, TLS warning behavior, and grouped UI rendering/export actions.

### Changed

- `fedora44-readiness` now routes through the generic readiness engine as a compatibility alias.
- The Atlas dashboard readiness entry point now opens the generic release readiness dialog.
- Support bundle generation now writes v4 payloads while preserving `fedora_kde_44_readiness` for older consumers.
- TLS certificate compatibility no longer warns when Fedora's CA trust bundle exists at `/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem`.

### Fixed

- Resolved the old duplicate `[6.0.0]` changelog heading by marking the historical entry as legacy.
- Closed the stale v5 workflow state by activating v6.0.0 "Compass" release specs.

## Stats

- **Targeted readiness/UI tests:** 26 passed, 0 failed
- **Full tests:** 7327 passed, 48 skipped, 182 subtests passed
- **Coverage gate:** 80.01% total coverage, meeting the 80% requirement
- **Release gates:** `just validate-release`, `just check-drift`, and stabilization scanner passed

## Upgrade Notes

- Use `loofi-fedora-tweaks --cli readiness --target 44` for the supported Fedora KDE 44 profile.
- Use `loofi-fedora-tweaks --cli readiness --target 45-preview` only for planning. It is advisory and non-blocking.
- `loofi-fedora-tweaks --cli fedora44-readiness` remains as a compatibility alias for one major release.
