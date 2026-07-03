# Architecture — v12.0.0 "Lighthouse"

## Goals

- Build a proactive, read-only My Fedora Today timeline on top of v11 Daily Maintenance and Action Center contracts.
- Persist bounded health snapshots safely under the existing XDG data directory pattern.
- Detect recurring, new, resolved, and worsening system health signals without storing private raw data.
- Surface trend-aware recommendations through Action Center without automatic repair or fix-all behavior.
- Preserve Fedora KDE 44 as the stable target and Fedora 45 as preview/advisory.

## Boundaries

- `core/observability/*` owns snapshot models, timeline storage, fingerprinting, trend analysis, and privacy redaction.
- `core/diagnostics/daily_maintenance.py` remains the read-only collection source for maintenance cards.
- `core/actions/*` remains the recommendation/action model. Timeline recommendations are manual-safe `ActionCenterItem` objects.
- `cli/main.py` exposes health and maintenance commands without importing UI modules.
- `daemon/*` and `api/routes/system.py` may collect snapshots, but only through read-only observability APIs.
- `ui/maintenance_tab.py` and `ui/atlas_dashboard_tab.py` provide entry points only; they do not run subprocesses directly.
- `core/export/support_bundle_v5.py` remains the compatibility implementation and emits the v12 Support Bundle v8 schema.

## Decisions

- Use JSON timeline storage instead of extending the older SQLite metric timeline because v12 snapshots are structured diagnostic reports, not numeric metric samples.
- Use normalized `ProblemFingerprint` IDs to dedupe failed services, journal warnings, package-manager problems, low disk, rollback gaps, and Action Center-derived findings.
- Store only bounded local history, defaulting to 30 snapshots.
- Treat corrupt timeline JSON as empty recovered history and report the recovery state instead of crashing.
- Keep mutating actions preview-first and confirmation-gated; timeline recommendations are manual-only unless a future explicit action contract is added.
- Preserve v5/v6/v7 support bundle compatibility keys while setting the current schema to `12.0.0-lighthouse-support-v8`.

## Non-goals

- No UI rewrite.
- No new permanent top-level sidebar category.
- No automatic package upgrades, firmware updates, cleanup, service restarts, or fix-all daemon behavior.
- No promotion of Fedora 45 to stable default.
- No removal of old support bundle import paths or compatibility fields.
