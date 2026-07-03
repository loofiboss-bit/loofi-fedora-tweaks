# Release Notes -- v12.0.0 "Lighthouse"

**Release Date:** 2026-07-03
**Codename:** Lighthouse
**Theme:** Proactive Fedora health observability and guided daily recovery

## Summary

v12.0.0 "Lighthouse" turns the v11 Action Center and Daily Maintenance system into a proactive health timeline. It records bounded, privacy-safe snapshots, detects recurring or resolved maintenance issues, and exports better support data without automatically mutating the system.

## Highlights

- My Fedora Today health timeline with schema versioning, retention, corrupt-history fallback, and privacy-safe export.
- Trend-aware recurring, new, resolved, and worsening issue detection using normalized fingerprints.
- Action Center v2 recommendations from health trends with dedupe keys, correlation IDs, grouping, and safe next steps.
- CLI commands for `health snapshot`, `health timeline`, `maintenance today`, and `action-center recommendations`.
- Optional daemon/API read-only snapshot collection.
- Support Bundle v8 with snapshot, timeline, recurring fingerprints, recommendations, daemon snapshot status, and redaction guarantees.

## Changes

### Changed

- Fedora KDE 44 remains the stable readiness target.
- Fedora 45 remains `45-preview` and advisory, not the default target.
- Existing route IDs, plugin IDs, CLI aliases, support bundle compatibility fields, favorites, and saved settings remain compatible.

### Added

- `core.observability` modules for health snapshots, timeline storage, fingerprints, trend analysis, and privacy redaction.
- Maintenance > Health Timeline and Home > My Fedora Today entry points.
- Action Center item fields for `dedupe_key`, `why_this_matters`, and `safe_next_step`.
- Daemon `ObservabilityCollectHealthSnapshot` and `ObservabilityHealthTimeline` methods.
- Authenticated API routes for `/observability/snapshot` and `/observability/timeline`.
- Focused tests for snapshot serialization, retention, corrupt history, trend detection, redaction, CLI JSON output, daemon read-only behavior, recommendations, and Support Bundle v8.

### Fixed

- Corrupt local health timeline data no longer crashes collection or export paths.
- Health timeline exports redact private paths, emails, hostnames, tokens, API keys, and secret-like values.
- Recurring journal warnings are deduplicated by normalized fingerprints instead of raw log lines.

## Stats

- **Tests:** Targeted v12 tests pass locally; full release gate results are recorded by CI.
- **Lint:** Validated by `just verify` and CI.
- **Coverage:** 84% minimum gate retained.

## Upgrade Notes

No migration is required. Existing settings, favorites, route IDs, CLI aliases, and support bundle compatibility fields are preserved. The new health timeline stores bounded local JSON under the existing XDG data directory pattern.
