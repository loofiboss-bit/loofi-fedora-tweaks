# Tasks — v11.0.0 "Harbor"

## Contract

- [x] ID: T1 | Files: version.py, pyproject.toml, loofi-fedora-tweaks.spec, metainfo, README.md, ROADMAP.md, CHANGELOG.md | Dep: none | Agent: release-planner | Description: Activate v11.0.0 Harbor release metadata
  Acceptance: Runtime, packaging, AppStream, roadmap, changelog, README, release notes, and race-lock all name v11.0.0 Harbor
  Tests: just validate-release

- [x] ID: T2 | Files: scripts/check_release_docs.py, tests/test_release_doc_check.py | Dep: T1 | Agent: verifier | Description: Extend release trust gate for AppStream and workflow codename drift
  Acceptance: validate-release fails if AppStream release entry or v11 workflow codename/version references are missing
  Tests: just test-file test_release_doc_check

- [x] ID: T3 | Files: core/actions/*, cli/main.py | Dep: T2 | Agent: core | Description: Add Unified Action Center model, queue, history, rollback guidance, and CLI preview surface
  Acceptance: Existing readiness action candidates can be represented, previewed, queued, and exported as Action Center items
  Tests: just test-file test_action_center

- [x] ID: T4 | Files: core/diagnostics/daily_maintenance.py | Dep: T3 | Agent: diagnostics | Description: Add read-only Daily Maintenance diagnostics
  Acceptance: Traditional and Atomic Fedora paths produce deterministic dashboard cards with package/update/rollback guidance
  Tests: just test-file test_daily_maintenance

- [x] ID: T5 | Files: core/export/support_bundle_v5.py, core/export/support_bundle_v7.py | Dep: T3,T4 | Agent: export | Description: Add Support Bundle v7 fields while preserving v5/v6 compatibility
  Acceptance: Bundle includes support_bundle_version 7, Action Center, rollback, maintenance, daemon/API, package health, and GitHub issue text data
  Tests: just test-file test_fedora44_readiness
