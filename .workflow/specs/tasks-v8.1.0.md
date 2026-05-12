# Tasks — v8.1.0

## Contract

- [x] ID: T1 | Files: ROADMAP.md, CHANGELOG.md, README.md, docs/releases/RELEASE-NOTES-v8.1.0.md | Dep: none | Agent: release-planner | Description: Activate v8.1.0 Breeze and document the UI redesign scope
  Acceptance: ROADMAP has exactly one ACTIVE release and current metadata reads 8.1.0 Breeze
  Docs: ROADMAP.md, CHANGELOG.md, README.md, docs/releases/RELEASE-NOTES-v8.1.0.md
  Tests: python3 scripts/check_release_docs.py

- [x] ID: T2 | Files: loofi-fedora-tweaks/core/navigation/areas.py, loofi-fedora-tweaks/core/navigation/__init__.py, loofi-fedora-tweaks/core/navigation/manifest.py, loofi-fedora-tweaks/utils/experience_level.py | Dep: T1 | Agent: navigator | Description: Add focused navigation areas without changing stable route IDs
  Acceptance: The default sidebar exposes Home, Software & Updates, System & Hardware, Network & Security, and Desktop & Settings while hidden advanced routes remain resolvable
  Docs: ARCHITECTURE.md, README.md
  Tests: just test-file test_navigation; just test-file test_experience_level

- [x] ID: T3 | Files: loofi-fedora-tweaks/ui/main_window.py, loofi-fedora-tweaks/ui/layout_primitives.py, loofi-fedora-tweaks/ui/atlas_dashboard_tab.py, loofi-fedora-tweaks/ui/settings_tab.py, loofi-fedora-tweaks/ui/tab_utils.py | Dep: T2 | Agent: ui-engineer | Description: Rework the PyQt shell around an airy focused sidebar, page header, responsive content stack, and shared layout primitives
  Acceptance: MainWindow supports wide, medium, and narrow breakpoints; favorites and direct route switching work for hidden default routes
  Docs: docs/USER_GUIDE.md, docs/BEGINNER_QUICK_GUIDE.md, docs/ADVANCED_ADMIN_GUIDE.md
  Tests: just test-file test_main_window; just test-file test_main_window_geometry; just test-file test_tab_margins; just test-file test_settings_tab_ux

- [x] ID: T4 | Files: loofi-fedora-tweaks/assets/modern.qss, loofi-fedora-tweaks/assets/light.qss, loofi-fedora-tweaks/assets/highcontrast.qss, loofi-fedora-tweaks/main.py | Dep: T3 | Agent: visual-systems | Description: Apply the Breeze spacing, contrast, selection, text wrapping, and startup-theme behavior across supported themes
  Acceptance: The app honors saved/system theme selection and avoids fixed-size clipping at Qt scale factors 1, 1.25, 1.5, and 2
  Docs: docs/releases/RELEASE-NOTES-v8.1.0.md
  Tests: just test-file test_main_window_geometry

- [x] ID: T5 | Files: scripts/check_packaging_manifest.py, tests/test_packaging_scripts.py | Dep: T2 | Agent: release-engineer | Description: Include new navigation and layout modules in packaging validation
  Acceptance: Packaging checks fail if the new modules are missing from source or wheel artifacts
  Docs: docs/releases/RELEASE-NOTES-v8.1.0.md
  Tests: just test-file test_packaging_scripts

- [x] ID: T6 | Files: docs/images/user-guide/*.png, wiki/images/*.png, docs/images/user-guide/README.md, wiki/Screenshots.md | Dep: T3 | Agent: docs | Description: Replace screenshots with captures from the redesigned Breeze UI
  Acceptance: User guide and wiki screenshots are regenerated from the PyQt app and reference v8.1.0 Breeze
  Docs: docs/images/user-guide/README.md, wiki/Screenshots.md
  Tests: file docs/images/user-guide/*.png wiki/images/*.png

- [x] ID: T7 | Files: README.md, docs/README.md, docs/USER_GUIDE.md, docs/BEGINNER_QUICK_GUIDE.md, docs/ADVANCED_ADMIN_GUIDE.md, wiki/*.md | Dep: T1,T2,T6 | Agent: docs | Description: Update user-facing documentation for the focused menu and release package state
  Acceptance: Current docs describe the five-area sidebar, advanced route access, v8.1.0 install expectations, and refreshed screenshots
  Docs: README.md, wiki/Home.md
  Tests: just validate-release

- [x] ID: T8 | Files: all release artifacts | Dep: T1-T7 | Agent: verifier | Description: Run local release gates before publishing
  Acceptance: lint, typecheck, tests, release validation, drift checks, packaging checks, and full verify pass locally
  Docs: docs/releases/RELEASE-NOTES-v8.1.0.md
  Tests: just lint; just typecheck; just test; just validate-release; just check-drift; just verify
