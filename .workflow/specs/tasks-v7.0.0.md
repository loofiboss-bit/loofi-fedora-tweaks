# Tasks — v7.0.0 "Aegis"

## Contract

- [x] ID: T1 | Files: version.py, pyproject.toml, spec, docs | Dep: none | Agent: Planner | Description: Align v7.0.0 Aegis metadata
  Acceptance: Runtime, packaging, changelog, roadmap, release notes, README, active workflow specs, and race-lock identify v7.0.0 "Aegis"
  Docs: README.md, CHANGELOG.md, ROADMAP.md, docs/releases/RELEASE-NOTES-v7.0.0.md
  Tests: scripts/check_release_docs.py

- [x] ID: T2 | Files: core/diagnostics/readiness_actions.py, core/diagnostics/release_readiness.py | Dep: T1 | Agent: Builder | Description: Add safe Guided Action Bridge
  Acceptance: Readiness findings produce reviewable action candidates, previews never mutate, manual-only actions cannot execute, and mutating actions require confirmation
  Docs: docs/FEDORA_KDE_44_READINESS.md
  Tests: tests/test_v7_aegis.py, tests/test_fedora44_readiness.py

- [x] ID: T3 | Files: cli/main.py, ui/release_readiness_dialog.py | Dep: T2 | Agent: Sculptor | Description: Surface action planning in CLI and existing readiness dialog
  Acceptance: CLI supports action inbox commands, default JSON excludes advanced detail, and GUI exposes action metadata without a fix-all flow
  Docs: README.md, docs/USER_GUIDE.md
  Tests: tests/test_v7_aegis.py, tests/test_v4_ui.py

- [x] ID: T4 | Files: core/export/support_bundle_v5.py, utils/journal.py | Dep: T2 | Agent: Builder | Description: Add Support Bundle v5
  Acceptance: Bundle includes release readiness, compatibility alias, action plan/history, package health, service/journal/Flatpak/Atomic/NVIDIA signals, and recursive privacy redaction
  Docs: docs/FEDORA_KDE_44_READINESS.md
  Tests: tests/test_v7_aegis.py

- [x] ID: T5 | Files: scripts/check_release_docs.py, .github/workflows/*.yml | Dep: T1 | Agent: Guardian | Description: Harden release gates
  Acceptance: CI and auto-release enforce coverage 80, docs-only changes run release-doc validation, and release metadata drift is detected
  Docs: docs/README.md
  Tests: tests/test_release_doc_check.py

- [x] ID: T6 | Files: docs/, .github/workflow/, .github/agent-memory/ | Dep: T1-T5 | Agent: Planner | Description: Refresh v7 docs and Fedora 44 wording
  Acceptance: Fedora KDE 44 is the supported target, Fedora 45 is preview-only, Plugin SDK prefers semantic icon IDs, and stale v6/v5 current-release claims are removed
  Docs: docs/FEDORA_KDE_44_READINESS.md, docs/PLUGIN_SDK.md
  Tests: just validate-release
