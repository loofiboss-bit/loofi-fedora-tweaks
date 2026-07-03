# Tasks — v12.0.0 "Lighthouse"

## Contract

- [x] ID: T1 | Files: version.py, pyproject.toml, loofi-fedora-tweaks.spec, metainfo, README.md, ROADMAP.md, CHANGELOG.md | Dep: none | Agent: release-planner | Description: Activate v12.0.0 Lighthouse release metadata
  Acceptance: Runtime, packaging, AppStream, roadmap, changelog, README, release notes, and race-lock all name v12.0.0 Lighthouse
  Docs: ROADMAP.md, docs/releases/RELEASE-NOTES-v12.0.0.md
  Tests: scripts/check_release_docs.py

- [x] ID: T2 | Files: core/observability/*, core/diagnostics/daily_maintenance.py | Dep: T1 | Agent: core | Description: Add My Fedora Today snapshot, timeline, fingerprint, trend, and privacy contracts
  Acceptance: Daily Maintenance reports convert into privacy-safe HealthSnapshot payloads, bounded storage survives corrupt JSON, and recurring fingerprints are stable
  Docs: ARCHITECTURE.md
  Tests: tests/test_health_snapshot.py, tests/test_health_timeline.py, tests/test_maintenance_trends.py, tests/test_observability_redaction.py

- [x] ID: T3 | Files: cli/main.py, daemon/*, api/routes/system.py | Dep: T2 | Agent: platform | Description: Expose read-only health snapshot and timeline flows in CLI, daemon, and API
  Acceptance: CLI commands are GUI-free and rootless, daemon/API collection is read-only, missing/corrupt history does not crash
  Docs: docs/releases/RELEASE-NOTES-v12.0.0.md
  Tests: tests/test_cli_health.py, tests/test_daemon_snapshot_collection.py

- [x] ID: T4 | Files: core/actions/*, ui/maintenance_tab.py, ui/atlas_dashboard_tab.py, core/navigation/manifest.py | Dep: T2 | Agent: ux | Description: Add Action Center v2 health recommendations and Maintenance/Home entry points
  Acceptance: Recommendations are deduped, manual-safe, grouped, linked to snapshot/fingerprint IDs, and visible from Maintenance without a new top-level sidebar area
  Docs: README.md
  Tests: tests/test_action_center_recommendations.py, tests/test_maintenance_tab.py

- [x] ID: T5 | Files: core/export/support_bundle_v5.py, core/export/support_bundle_v8.py | Dep: T2,T4 | Agent: support | Description: Add Support Bundle v8 observability fields while preserving compatibility import paths and keys
  Acceptance: Bundle includes schema 12.0.0-lighthouse-support-v8, latest snapshot, timeline, recurring fingerprints, recommendations, daemon snapshot status, and redacted issue text
  Docs: docs/releases/RELEASE-NOTES-v12.0.0.md
  Tests: tests/test_support_bundle_v8.py, tests/test_fedora44_readiness.py

- [x] ID: T6 | Files: core/diagnostics/release_targets.py, docs/FEDORA_KDE_44_READINESS.md | Dep: T1 | Agent: readiness | Description: Preserve Fedora KDE 44 default and Fedora 45 preview/advisory behavior
  Acceptance: Target 44 remains default, 45-preview remains non-blocking, support bundle can carry preview context
  Docs: docs/FEDORA_KDE_44_READINESS.md
  Tests: tests/test_fedora44_readiness.py

- [x] ID: T7 | Files: docs/plans/v12.0.0-lighthouse-plan.md, docs/releases/RELEASE-NOTES-v12.0.0.md, .workflow/specs/*v12.0.0.md | Dep: T1-T6 | Agent: release | Description: Complete release documentation and validation artifacts
  Acceptance: Release docs, workflow specs, race-lock, changelog, README, spec, and AppStream metadata are aligned for v12 publication
  Docs: docs/releases/RELEASE-NOTES-v12.0.0.md
  Tests: just validate-release
