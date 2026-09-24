# Tasks — v30.1.0 "Personalize"

## Implementation

- [x] ID: T1 | Files: `ui/navigation/destination_sidebar.py`, `ui/main_window_utility.py` | Dep: none | Agent: Codex | Description: Relabel five primary routes and retain aliases.
  Acceptance: Old and new routes resolve to owning pages.
  Docs: `ARCHITECTURE.md`
  Tests: `tests/test_v29_shell.py`
- [x] ID: T2 | Files: `core/tasks/tweaks.py`, `core/actions/tweaks.py`, `core/executor/command_policy.py` | Dep: T1 | Agent: Codex | Description: Define eight closed state-backed controls and verified actions.
  Acceptance: Unknown values and unreviewed settings fail closed.
  Docs: `docs/USER_GUIDE.md`
  Tests: `tests/test_tweaks_v30_1.py`
- [x] ID: T3 | Files: `ui/tweaks_page.py`, `ui/main_window_utility.py` | Dep: T2 | Agent: Codex | Description: Apply one selected value on its row and refresh actual state.
  Acceptance: Saved appears only after independent readback.
  Docs: `docs/BEGINNER_QUICK_GUIDE.md`
  Tests: `tests/test_tweaks_v30_1.py`
- [x] ID: T4 | Files: `ui/fix_workflow.py`, `ui/main_window.py`, `core/tasks/catalog.py` | Dep: T1 | Agent: Codex | Description: Move maintenance and repair reviews to Health.
  Acceptance: Normal requests remain on Health; findings are re-resolved.
  Docs: `ARCHITECTURE.md`
  Tests: `tests/test_v29_shell.py`, `tests/test_tweaks_v30_1.py`

## Qualification

- [x] ID: Q1 | Files: none | Dep: T1-T4 | Agent: Codex | Description: Complete offscreen verify, stats, docs, and packaging gates.
  Acceptance: Exact commands and outcomes recorded in candidate notes.
  Docs: `docs/releases/RELEASE-NOTES-v30.1.0.md`
  Tests: `just verify`, `just stats-check`, `just validate-release`, `just check-packaging`
- [ ] ID: Q2 | Files: none | Dep: Q1 | Agent: Physical tester | Description: Test live GNOME, KDE, Polkit, keyboard, and scaling.
  Acceptance: Each physical result is separately evidenced.
  Docs: `docs/releases/RELEASE-NOTES-v30.1.0.md`
  Tests: physical desktop sessions
