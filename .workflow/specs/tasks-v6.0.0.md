# Tasks — v6.0.0

## Contract

- [x] ID: T1 | Files: version.py, pyproject.toml, spec, docs | Dep: none | Agent: Planner | Description: Align v6.0.0 Compass metadata
  Acceptance: Runtime, packaging, changelog, roadmap, release notes, and active workflow specs identify v6.0.0 "Compass"
  Docs: README.md, CHANGELOG.md, ROADMAP.md, docs/releases/RELEASE-NOTES-v6.0.0.md
  Tests: just validate-release

- [x] ID: T2 | Files: core/diagnostics/release_readiness.py, core/diagnostics/fedora44_readiness.py | Dep: T1 | Agent: Builder | Description: Replace Fedora-44-only readiness with generic target metadata
  Acceptance: Fedora KDE 44 is supported, Fedora 45 preview is advisory, and the old Fedora44Readiness import remains compatible
  Docs: docs/FEDORA_KDE_44_READINESS.md
  Tests: tests/test_fedora44_readiness.py

- [x] ID: T3 | Files: core/diagnostics/release_readiness.py | Dep: T2 | Agent: Guardian | Description: Attach typed recommendation metadata to readiness findings
  Acceptance: Findings can expose command preview, risk, reversibility, rollback, docs, and manual-only flags without executing repair commands
  Docs: docs/FEDORA_KDE_44_READINESS.md
  Tests: tests/test_fedora44_readiness.py

- [x] ID: T4 | Files: ui/release_readiness_dialog.py, ui/fedora44_readiness_dialog.py, ui/atlas_dashboard_tab.py, core/diagnostics/task_dashboard.py | Dep: T2 | Agent: Sculptor | Description: Build grouped readiness UI
  Acceptance: Dialog renders grouped findings, severity filters, beginner/advanced details, async refresh, copy summary, and export action
  Docs: README.md
  Tests: tests/test_v4_ui.py

- [x] ID: T5 | Files: cli/main.py | Dep: T2 | Agent: Builder | Description: Add generic readiness CLI and compatibility alias
  Acceptance: `readiness --target 44|45-preview` works; `fedora44-readiness` remains available
  Docs: README.md, docs/FEDORA_KDE_44_READINESS.md
  Tests: tests/test_fedora44_readiness.py

- [x] ID: T6 | Files: core/export/support_bundle_v4.py, core/export/support_bundle_v3.py, ui/support_bundle_wizard.py, utils/journal.py | Dep: T2 | Agent: Builder | Description: Add support bundle v4 with v3 aliases
  Acceptance: Bundle includes `release_readiness` and legacy `fedora_kde_44_readiness` fields
  Docs: docs/FEDORA_KDE_44_READINESS.md
  Tests: tests/test_fedora44_readiness.py, tests/test_v4_ui.py

- [x] ID: T7 | Files: tests/ | Dep: T2-T6 | Agent: Guardian | Description: Add regression coverage and release gates
  Acceptance: Targeted tests cover metadata, scoring, aliases, support bundle v4, Fedora 45 preview, TLS warning behavior, and UI actions
  Docs: docs/releases/RELEASE-NOTES-v6.0.0.md
  Tests: just test, just test-coverage
