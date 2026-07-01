# Tasks — v9.0.0

## Contract

- [x] ID: T1 | Files: ROADMAP.md, CHANGELOG.md, README.md, docs/releases/RELEASE-NOTES-v9.0.0.md | Dep: none | Agent: release-planner | Description: Activate v9.0.0 Keystone as a whole-app quality release
  Acceptance: ROADMAP has exactly one ACTIVE release, metadata reads 9.0.0 Keystone, and docs do not promote Fedora 45 as the main target
  Docs: ROADMAP.md, CHANGELOG.md, docs/releases/RELEASE-NOTES-v9.0.0.md
  Tests: python3 scripts/check_release_docs.py

- [x] ID: T2 | Files: Justfile, .github/workflows/ci.yml, .github/workflows/auto-release.yml, scripts/check_release_docs.py | Dep: T1 | Agent: release-engineer | Description: Raise and synchronize the release coverage gate to 84%
  Acceptance: Local and CI release surfaces enforce the same 84% minimum and docs claims do not exceed enforcement
  Docs: README.md, docs/releases/RELEASE-NOTES-v9.0.0.md
  Tests: just validate-release; just test-file test_release_doc_check

- [x] ID: T3 | Files: loofi-fedora-tweaks/core/executor/command_facade.py, loofi-fedora-tweaks/core/executor/__init__.py | Dep: T1 | Agent: platform | Description: Add a narrow command facade over ActionExecutor and command policy
  Acceptance: Preview and execute accept command vectors, reject shell-style commands, preserve timeout/action metadata, and keep pkexec handling at the executor boundary
  Docs: ARCHITECTURE.md
  Tests: just test-file test_action_executor

- [x] ID: T4 | Files: loofi-fedora-tweaks/core/diagnostics/release_readiness.py, tests/test_fedora44_readiness.py | Dep: T1 | Agent: diagnostics | Description: Lock readiness defaults to Fedora KDE 44 while keeping Fedora 45 preview-only
  Acceptance: ReleaseReadiness.run() defaults to target 44 and TARGETS["45-preview"] remains unsupported preview metadata
  Docs: docs/FEDORA_KDE_44_READINESS.md, docs/releases/RELEASE-NOTES-v9.0.0.md
  Tests: just test-file test_fedora44_readiness

- [x] ID: T5 | Files: loofi-fedora-tweaks/core/navigation/manifest.py, tests/test_navigation.py | Dep: T1 | Agent: navigator | Description: Extend route/plugin trust regression coverage without renaming route IDs
  Acceptance: Hidden routes remain searchable, quick actions and palette routes stay in manifest parity, and plugin metadata references remain stable
  Docs: ARCHITECTURE.md
  Tests: just test-file test_navigation

- [x] ID: T6 | Files: ARCHITECTURE.md, tests/test_architecture_imports.py | Dep: T3 | Agent: architecture | Description: Document and test explicit Qt runtime exceptions in core/plugin worker plumbing
  Acceptance: Architecture boundaries are clear, known exceptions are allowlisted, and no untracked PyQt imports are introduced into core/services
  Docs: ARCHITECTURE.md
  Tests: just test-file test_architecture_imports

- [x] ID: T7 | Files: docs/README.md, docs/TROUBLESHOOTING.md, docs/STRATEGIC_PLAN_V10.md, wiki/Home.md | Dep: T1 | Agent: docs | Description: Refresh user/developer docs for v9 quality scope and mark stale planning material historical
  Acceptance: Current docs describe v9 as app-wide quality work and stale v10 assumptions are not presented as current
  Docs: README.md, docs/README.md, docs/TROUBLESHOOTING.md
  Tests: just validate-release

- [x] ID: T8 | Files: all release artifacts | Dep: T1-T7 | Agent: verifier | Description: Run focused release gates before handoff
  Acceptance: targeted regression tests, release validation, stabilization rules, drift check, lint/typecheck as feasible, and package manifest checks pass locally
  Docs: docs/releases/RELEASE-NOTES-v9.0.0.md
  Tests: just lint; just typecheck; just test-coverage; just validate-release; just check-drift; just check-packaging
