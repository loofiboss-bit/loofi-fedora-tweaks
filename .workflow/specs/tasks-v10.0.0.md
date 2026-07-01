# Tasks — v10.0.0

## Contract

- [x] ID: T1 | Files: version.py, pyproject.toml, loofi-fedora-tweaks.spec, ROADMAP.md, CHANGELOG.md, README.md | Dep: none | Agent: release-planner | Description: Activate v10.0.0 Waypoint release metadata
  Acceptance: Version metadata, roadmap active release, changelog, README, spec, and release notes all name v10.0.0 Waypoint
  Tests: just validate-release

- [x] ID: T2 | Files: core/diagnostics/release_readiness.py | Dep: T1 | Agent: diagnostics | Description: Expand release target metadata and Fedora 45 preview planning checks
  Acceptance: Fedora 44 remains default; Fedora 45 preview reports release changes and advisory checks without mutating the system
  Tests: just test-file test_fedora44_readiness

- [x] ID: T3 | Files: cli/main.py, core/export/support_bundle_v5.py | Dep: T2 | Agent: cli | Description: Add readiness plan, explain, export, and Support Bundle v6 payload fields
  Acceptance: CLI commands support text and JSON output; support bundle preserves v5 fields and adds v6 release-planning data
  Tests: just test-file test_fedora44_readiness

- [x] ID: T4 | Files: ui/atlas_dashboard_tab.py, ui/maintenance_tab.py, ui/release_readiness_dialog.py, core/navigation/manifest.py | Dep: T2 | Agent: ux | Description: Add Home and Maintenance Upgrade Assistant entry points
  Acceptance: Existing Maintenance plugin exposes `maintenance:upgrade-assistant`; dialog shows target changes and existing action inbox/export behavior
  Tests: just test-file test_navigation

- [x] ID: T5 | Files: utils/update_manager.py, ui/maintenance_tab.py | Dep: T4 | Agent: maintenance | Description: Harden Smart Updates display and scheduled update command generation
  Acceptance: Smart Updates uses actual dataclass fields and scheduled service commands are built from validated arguments
  Tests: just test-file test_update_manager

- [x] ID: T6 | Files: docs/releases/RELEASE-NOTES-v10.0.0.md, .workflow/specs/*v10.0.0.md | Dep: T1-T5 | Agent: verifier | Description: Run v10 validation gates
  Acceptance: Release docs, navigation, readiness, CLI, and update-manager regressions pass locally
  Tests: just validate-release; just check-drift; just lint; just typecheck; just test-coverage
