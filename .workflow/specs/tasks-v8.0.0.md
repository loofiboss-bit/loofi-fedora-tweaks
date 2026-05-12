# Tasks — v8.0.0

## Contract

- [x] ID: T1 | Files: ROADMAP.md, CHANGELOG.md, README.md, docs/releases/RELEASE-NOTES-v8.0.0.md | Dep: none | Agent: release-planner | Description: Activate v8.0.0 Beacon and mark v7.0.0 Aegis done
  Acceptance: ROADMAP has exactly one ACTIVE release and current metadata reads 8.0.0 Beacon
  Docs: ROADMAP.md, CHANGELOG.md, README.md
  Tests: scripts/check_release_docs.py

- [x] ID: T2 | Files: loofi-fedora-tweaks/core/navigation/* | Dep: T1 | Agent: architect | Description: Add PyQt-free navigation route manifest
  Acceptance: Route IDs are unique, aliases resolve, plugin IDs are valid, risk/visibility values are constrained, and required subroutes exist
  Docs: ARCHITECTURE.md
  Tests: tests/test_navigation.py

- [x] ID: T3 | Files: loofi-fedora-tweaks/ui/main_window.py, loofi-fedora-tweaks/ui/lazy_widget.py | Dep: T2 | Agent: ui-engineer | Description: Add route-aware sidebar switching, breadcrumbs, and icon-only collapsed sidebar
  Acceptance: switch_to_route works for plugin and subroute IDs; switch_to_tab remains compatible with legacy labels
  Docs: ARCHITECTURE.md
  Tests: tests/test_main_window.py

- [x] ID: T4 | Files: loofi-fedora-tweaks/ui/command_palette.py, loofi-fedora-tweaks/ui/quick_actions.py, loofi-fedora-tweaks/ui/dashboard_tab.py, loofi-fedora-tweaks/ui/atlas_dashboard_tab.py, loofi-fedora-tweaks/utils/quick_actions_config.py | Dep: T2 | Agent: ui-engineer | Description: Route command palette, quick actions, dashboard cards, and legacy config migration through the manifest
  Acceptance: Every command palette and quick action navigation target resolves to a valid route ID
  Docs: docs/releases/RELEASE-NOTES-v8.0.0.md
  Tests: tests/test_command_palette_actions.py, tests/test_quick_actions.py, tests/test_quick_actions_config.py

- [x] ID: T5 | Files: loofi-fedora-tweaks/utils/favorites.py, loofi-fedora-tweaks/ui/main_window.py | Dep: T2 | Agent: ui-engineer | Description: Persist Favorites v2 as stable route/plugin IDs and migrate legacy values
  Acceptance: Favorites survive reload, preserve order, and drop unknown legacy entries with a warning
  Docs: docs/releases/RELEASE-NOTES-v8.0.0.md
  Tests: tests/test_favorites.py

- [x] ID: T6 | Files: loofi-fedora-tweaks/core/executor/command_policy.py, loofi-fedora-tweaks/core/executor/action_executor.py, loofi-fedora-tweaks/api/routes/executor.py, loofi-fedora-tweaks/utils/profiles.py, scripts/check_stabilization_rules.py | Dep: none | Agent: safety | Description: Enforce shared command allowlist and snapshot command validation
  Acceptance: Preview and execute reject unsafe commands; sudo, shell interpreters, empty/path-separated commands, shell=True, and UI subprocess drift are blocked by tests/gates
  Docs: ARCHITECTURE.md
  Tests: tests/test_action_executor.py, tests/test_profiles.py, tests/test_check_stabilization_rules.py

- [x] ID: T7 | Files: pyproject.toml, MANIFEST.in, scripts/check_packaging_manifest.py, loofi-fedora-tweaks.spec, Justfile, .github/workflows/*.yml | Dep: T1 | Agent: packaging | Description: Harden wheel/sdist/RPM release gates
  Acceptance: RPM import check is blocking; packaging manifest gate verifies expected packages, assets, translations, resources, and entry point metadata
  Docs: docs/releases/RELEASE-NOTES-v8.0.0.md
  Tests: tests/test_release_doc_check.py, tests/test_packaging_scripts.py

- [x] ID: T8 | Files: loofi-fedora-tweaks/assets/*.qss, loofi-fedora-tweaks/ui/icon_pack.py, loofi-fedora-tweaks/ui/virtualization_tab.py | Dep: T3 | Agent: ui-polish | Description: Improve navigation visuals and keep virtualization in the live plugin registry
  Acceptance: Sidebar polish uses objectName/QSS where practical, every route icon resolves or has a documented fallback, and virtualization loads as a built-in plugin
  Docs: ARCHITECTURE.md
  Tests: tests/test_navigation.py, tests/test_ui_tab_smoke.py
