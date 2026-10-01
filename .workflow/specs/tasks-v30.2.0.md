# Tasks — v30.2.0 "Comfort"

Baseline: v30.1.0 master `737a550`. Local implementation is qualified. On 2026-10-01 the user authorized full
GitHub, COPR, and wiki publication. Workstation installation remains outside scope.

## Implementation

- [x] ID: T1 | Files: `core/tasks/tweaks.py`, `core/actions/tweaks.py`, `core/executor/command_policy.py` | Dep: none | Agent: Codex | Description: Add six closed controls and narrow typed policy.
  Acceptance: Fourteen definitions; seven KDE and eight GNOME rows; unknown/bootc blocked.
  Docs: `docs/USER_GUIDE.md`
  Tests: focused tweak tests and Traditional/Atomic desktop matrix
- [x] ID: T2 | Files: `core/actions/tweaks.py`, `core/tasks/tweaks.py` | Dep: T1 | Agent: Codex | Description: Add durable metadata and source-only verified restoration.
  Acceptance: Exact custom values preserved; drift/later attempts/legacy or missing history blocked; successful restore consumed.
  Docs: `ARCHITECTURE.md`, `docs/STATE_INTEGRITY.md`
  Tests: restart, precision, drift, removed choices, timeout, cancellation, storage failure
- [x] ID: T3 | Files: `ui/tweaks_page.py`, `ui/main_window_utility.py` | Dep: T2 | Agent: Codex | Description: Add row restoration confirmation and saved-configuration feedback.
  Acceptance: No success without verification; overlapping operations blocked; current and previous values visible.
  Docs: `docs/BEGINNER_QUICK_GUIDE.md`
  Tests: offscreen UI/controller tests
- [x] ID: T4 | Files: version metadata, active guides, release documents, wiki | Dep: T1-T3 | Agent: Codex | Description: Synchronize Comfort identity and local authority.
  Acceptance: Documentation validator and wiki mirror check pass; no publication claim.
  Docs: `docs/releases/RELEASE-NOTES-v30.2.0.md`
  Tests: `just validate-release`, `python3 scripts/sync_wiki_docs.py --check`

## Qualification

- [x] ID: Q1 | Files: none | Dep: T1-T4 | Agent: Codex | Description: Run full verification and build local RPM/source artifacts.
  Acceptance: Exact outcomes and 85% coverage recorded; packaged CLI/version checked without installation.
  Docs: `docs/reports/V30.2.0_LOCAL_QUALIFICATION.md`
  Tests: `just verify`, `just validate-release`, `just stats-check`, `just check-drift`, `just check-packaging`, `git diff --check`, RPM/source build
- [ ] ID: Q2 [post-publish] | Files: none | Dep: Q1 | Agent: Physical tester | Description: Qualify physical KDE/GNOME, Traditional/Atomic, keyboard, scaling, and Orca.
  Acceptance: Independent evidence per physical check; unperformed checks remain unverified.
  Docs: `docs/reports/V30.2.0_LOCAL_QUALIFICATION.md`
  Tests: physical desktop sessions

## Publication

- [ ] ID: P1 [post-publish] | Files: release evidence and active documentation | Dep: Q1 | Agent: Codex | Description: Publish through the canonical master pipeline and independently read back tag lineage, GitHub assets/checksums/attestation, COPR build/package/repository, and public wiki.
  Acceptance: Every named surface verified; immutable release tag retained; physical checks remain unverified.
  Docs: `docs/reports/V30.2.0_RELEASE_PUBLICATION.md`
  Tests: canonical release pipeline and independent public readback
