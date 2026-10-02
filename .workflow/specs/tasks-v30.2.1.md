# Tasks — v30.2.1 "Comfort" Local Candidate

Baseline: v30.2.0 commit `15967f2`. Local implementation, verification,
and RPM/source artifacts are authorized. A subsequent user request authorizes
commit, push, and pull request creation. Public release remains v30.2.0.
The qualification report records completed checks; this checklist does not
claim publication, workstation installation, or physical qualification.

## Implementation

- [x] ID: T1 | Files: `utils/journal.py`, `core/executor/action_executor.py`, regression tests | Dep: none | Agent: Codex | Description: Redact all archive members, publish atomically, and lock private logs.
  Acceptance: All synthetic secrets/paths/network identifiers are masked; collection/write failures are explicit; prior exports survive failure; log files are private and concurrent writes preserve entries.
  Docs: `docs/releases/RELEASE-NOTES-v30.2.1.md`
  Tests: archive-member inspection, failed collection/replacement, permissions, concurrent log writers
- [x] ID: T2 | Files: `core/actions/stores.py`, storage regression tests | Dep: none | Agent: Codex | Description: Reject corrupt plan writes and migration while retaining recovery evidence.
  Acceptance: Malformed JSON, schema shape, and invalid records leave original and backup bytes unchanged; errors provide recovery guidance.
  Docs: `docs/STATE_INTEGRITY.md`
  Tests: corrupt/future/legacy store preservation and denied save/migration
- [x] ID: T3 | Files: diagnostic collectors and System Check, regression tests | Dep: none | Agent: Codex | Description: Preserve valid findings alongside failed source probes and parse disk use correctly.
  Acceptance: 89/90/95/96-percent cases classify correctly; timeout/denied/malformed/nonzero probes remain explicit; useful findings survive partial collection.
  Docs: `docs/releases/RELEASE-NOTES-v30.2.1.md`
  Tests: percent thresholds, probe errors, mixed findings and source failures
- [x] ID: T4 | Files: Activity/Apps Qt adapters and UI regression tests | Dep: none | Agent: Codex | Description: Stabilize worker lifetime, validate dates, and preserve hidden app selections.
  Acceptance: Slow/error/cancel close and destruction survive in separate processes; invalid dates start no worker; review includes hidden selections and prunes changed eligibility.
  Docs: `docs/USER_GUIDE.md`
  Tests: offscreen lifecycle subprocesses, date validation, filtering/context/selection regressions
- [x] ID: T5 | Files: firmware assurance and structured evidence, regression tests | Dep: none | Agent: Codex | Description: Bind reviewed firmware targets and verification to device history.
  Acceptance: Current versions are distinct from targets; GUIDs remain lists; identity/version/checksum/status match the same record; insufficient old plans require new review.
  Docs: `.workflow/specs/arch-v30.2.1.md`
  Tests: realistic multi-device candidates/history, failed/pending/successful states, pre/post-reboot verification
- [x] ID: T6 | Files: version metadata, manual, current guides and release/workflow docs | Dep: T1-T5 | Agent: Codex | Description: Synchronize local candidate identity and authority.
  Acceptance: Version/spec/project/AppStream/manual agree; five destinations/eight CLI/fourteen tweaks/schema v4 remain; v30.2.0 stays public and all physical gates remain unverified.
  Docs: `README.md`, `docs/README.md`, `ROADMAP.md`, `CHANGELOG.md`
  Tests: release-doc validator, stats/adapters consistency, wiki mirror, diff check

## Local qualification

- [x] ID: Q1 | Files: qualification report and isolated build artifacts | Dep: T1-T6 | Agent: Codex | Description: Run full automated verification and build/read back local RPM/source packages.
  Acceptance: Exact tests/coverage and artifacts are recorded; installed RPM info/doctor smoke is read-only and isolated; no workstation installation.
  Docs: `docs/reports/V30.2.1_LOCAL_QUALIFICATION.md`
  Tests: `just verify`, `just check-packaging`, `just validate-release`, `just stats-check`, `just check-drift`, local RPM/source builds, isolated packaged CLI smoke

Physical/manual tests and remote publication require separate authority and
are not local delivery tasks. Retired-module cleanup, AppImage, and the broader
Fedora package matrix are deferred.
