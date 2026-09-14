# Tasks — v28.0.1 "Ease"

Status: release candidate. The review fixes and deterministic qualification are
being prepared for the authorized canonical publication workflow; physical
host qualification remains a separately tracked, explicitly unverified gate.

## P0 — trustworthy platform and state contracts

- [x] ID: EASE-001 | Files: `core/platform/profile.py`, `core/fedora_release_policy.py`, `services/system/onboarding.py`, `cli/commands/diagnostic_commands.py` | Dep: none | Agent: implementation | Description: Centralize Fedora 43/44 supported, Fedora 45 preview, and unknown release classification and carry the typed deployment backend through readiness and doctor surfaces.
  Acceptance: DNF, rpm-ostree, bootc, and unknown paths remain distinct; unknown release or backend never becomes an executable traditional update path.
  Docs: `ARCHITECTURE.md`, `docs/releases/RELEASE-NOTES-v28.0.1.md`
  Tests: `tests/test_platform_profile.py`, `tests/test_v27_platform_profile.py`, `tests/test_v27_doctor.py`, `tests/test_v15_phase7_onboarding.py`
- [x] ID: EASE-002 | Files: `services/software/update_overview.py`, `ui/update_overview.py`, `ui/maintenance_updates.py` | Dep: EASE-001 | Agent: implementation | Description: Make update inspection source-owned, cancellable, retryable, and backend-aware, with at most three concurrent read-only probes and immediate partial result publication.
  Acceptance: bootc and unknown backends receive manual/unavailable guidance; completed source results remain visible; a failed or cancelled probe does not turn a previous observation into “no updates”.
  Docs: `.workflow/specs/arch-v28.0.1.md`, `docs/VERIFIED_MAINTENANCE.md`
  Tests: `tests/test_update_overview.py`, `tests/test_update_overview_ui.py`, `tests/test_maintenance_updates_regression.py`, `tests/test_v24_flow_software.py`, `tests/test_v27_ux_contracts.py`
- [x] ID: EASE-003 | Files: `utils/history.py`, `core/change_journal/sources.py`, `core/change_journal/service.py`, `core/change_journal/models.py` | Dep: none | Agent: implementation | Description: Preserve valid history entries while reporting partial reads, distinguish unreadable storage from empty history, and expose an opaque continuation cursor.
  Acceptance: corrupt and future-schema history is unavailable; partially valid history remains inspectable and marked partial; journal pages are bounded and return a continuation marker.
  Docs: `docs/STATE_INTEGRITY.md`, `.workflow/specs/arch-v28.0.1.md`
  Tests: `tests/test_history.py`, `tests/test_change_journal.py`
- [x] ID: EASE-004 | Files: `tests/conftest.py`, `tests/test_platform_profile.py`, `tests/test_v15_phase7_onboarding.py` | Dep: none | Agent: implementation | Description: Isolate the shared suite from user XDG state and update release-policy expectations.
  Acceptance: tests use temporary config, data, cache, state, and home roots and do not read saved host history.
  Docs: `.workflow/specs/arch-v28.0.1.md`
  Tests: full `pytest` suite with the shared isolated fixture

## P1 — daily workflow ease

- [x] ID: EASE-005 | Files: `ui/maintenance_updates.py`, `ui/update_overview.py` | Dep: EASE-002 | Agent: implementation | Description: Make fresh source actions display a direct Review updates affordance while retaining the separate Action Center review, run, and verification lifecycle.
  Acceptance: a fresh source opens its review path with one clear action; stale, missing, unsupported, and unchecked sources remain unavailable with a next step.
  Docs: `README.md`, `docs/USER_GUIDE.md`, `ARCHITECTURE.md`
  Tests: `tests/test_v24_flow_software.py`, `tests/test_v27_ux_contracts.py`, `tests/test_update_overview_ui.py`
- [x] ID: EASE-006 | Files: `core/navigation/search.py`, `tests/test_global_search_model.py` | Dep: none | Agent: implementation | Description: Build action search results from the active Action Center catalog and support order-independent task phrases for free disk space, updates, and slow system.
  Acceptance: search does not maintain a competing executable-action list and routes results to the existing maintenance or review surfaces.
  Docs: `docs/USER_GUIDE.md`, `.workflow/specs/arch-v28.0.1.md`
  Tests: `tests/test_global_search_model.py`, `tests/test_global_search_ui.py`
- [x] ID: EASE-007 | Files: `ui/activity_recovery_tab.py`, `cli/parser_domains/observability.py`, `cli/commands/activity_commands.py`, `core/change_journal/presentation.py` | Dep: EASE-003 | Agent: implementation | Description: Add result/status filters and 25-record Load more pagination while retaining selection and position across appended pages.
  Acceptance: GUI and CLI pass the opaque cursor without interpreting source internals; partial and unavailable source status remains visible.
  Docs: `docs/USER_GUIDE.md`, `docs/STATE_INTEGRITY.md`
  Tests: `tests/test_change_journal.py`, `tests/test_activity_recovery_tab.py`, `tests/test_cli_parser_contract.py`
- [x] ID: EASE-008 | Files: `ui/action_center_presentation.py`, `core/actions/orchestrator.py`, `core/navigation/models.py` | Dep: EASE-001 | Agent: implementation | Description: Present plain-language change scope, authorization, restart, recovery, checked result, and next-step facts while failing closed for unknown and bootc mutation paths.
  Acceptance: technical output is secondary to the user-readable result; no direct mutator bypasses Changes.
  Docs: `docs/VERIFIED_MAINTENANCE.md`, `ARCHITECTURE.md`
  Tests: `tests/test_action_center.py`, `tests/test_action_center_assurance.py`, `tests/test_action_center_v14.py`, `tests/test_v27_ux_contracts.py`

## Compatibility and maintenance

- [x] ID: EASE-009 | Files: `core/home/service.py`, `utils/history.py` | Dep: EASE-003 | Agent: implementation | Description: Keep application-owned history on the current XDG state path and preserve v27 history/cache readers and migrations.
  Acceptance: old durable data remains readable, future schemas remain read-only, and no executable legacy undo vector is restored.
  Docs: `docs/STATE_INTEGRITY.md`
  Tests: `tests/test_history.py`, `tests/test_home_service.py`, `tests/test_update_overview.py`
- [x] ID: EASE-010 | Files: version metadata, `.workflow/specs`, release documentation | Dep: EASE-001–EASE-009 | Agent: implementation | Description: Establish the first new candidate as v28.0.1 "Ease" while preserving the historical v28.0.0 workflow-reset record and v27.0.1 public evidence.
  Acceptance: version.py, spec, pyproject, race lock, task spec, architecture spec, changelog, metainfo, README, roadmap, and release-note index agree on candidate status.
  Docs: `docs/releases/RELEASE-NOTES-v28.0.1.md`, `ROADMAP.md`
  Tests: `scripts/check_release_docs.py`, `scripts/bump_version.py --check`
- [ ] [post-publish] ID: EASE-011 | Files: qualification reports and workflow evidence | Dep: EASE-001–EASE-010 | Agent: release qualification | Description: Record the maintained-surface 90% coverage target, packaging checks, benchmark comparison, and the documented Fedora 43/44 KDE/GNOME and rpm-ostree matrix.
  Acceptance: coverage and performance thresholds are evidenced without excluding new code; RPM/sdist checks pass; all advertised host matrices have read-back evidence.
  Docs: `docs/reports/V28_EASE_QUALIFICATION.md`
  Tests: `just verify`, `just check-packaging`, `just build-rpm`, `just build-sdist`, physical test matrix
- [ ] [post-publish] ID: EASE-012 | Files: qualification reports and release surfaces | Dep: EASE-011 | Agent: release qualification | Description: Record Polkit allow/deny/cancel, real reboot verification, Orca, keyboard, light/dark, 100–200% scale, small-screen, and five-user-session gates when those physical sessions are available.
  Acceptance: physical/manual evidence is recorded for every advertised environment; offscreen evidence is not substituted for host proof.
  Docs: `docs/reports/V28_EASE_QUALIFICATION.md`
  Tests: documented physical Fedora sessions

## Explicit boundaries

- Commit, push, tag, GitHub release, and COPR publication are authorized for
  this release request. Host package installation, reboot, desktop-setting
  changes, background services, and new runtime dependencies remain outside
  the release workflow.
- Unchecked tasks are release gates, not evidence that the local implementation
  was skipped. They require a separately authorized qualification run.
