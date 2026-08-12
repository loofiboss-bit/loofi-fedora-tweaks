# Tasks — v25.0.4 “Proof”

Status: complete; v25.0.4 public release and independent publication readback
passed. Historical v25.0.0–v25.0.3 tags remain untouched.

## Phase 0 — baseline and release identity

- [x] T0.1 Record the v24 Flow baseline and exact historical v25 tag collisions.
- [x] T0.2 Select the first unused v25 patch identity, v25.0.4, without moving
  or deleting historical tags.

## Phase 1 — contracts and settings

- [x] T1.1 Add typed eligibility result and metadata audit with fail-closed behavior.
- [x] T1.2 Add versioned atomic Safety & Execution settings and safe migration/future-schema handling.
- [x] T1.3 Add Outcome Evidence contracts and state classification.

## Phase 2 — direct execution

- [x] T2.1 Implement `DirectActionService` over Action Center plan/run/verify authority.
- [x] T2.2 Preserve leases, expiry, confirmation, audit, correlation, interruption, recovery, and no auto-retry semantics.
- [x] T2.3 Add regression tests for unknown, manual-only, high-risk, unsupported, dry-run, preflight, reboot, verification-failure, and no-bypass cases.

## Phase 3 — CLI and GUI integration

- [x] T3.1 Add `run ACTION_ID [--param KEY=VALUE] [--yes] [--dry-run] [--json]` and stable exit/envelope contracts.
- [x] T3.2 Integrate high-traffic GUI routes through the same service with responsive single-flight workers.
- [x] T3.3 Add Safety & Execution controls inside the existing Settings destination.
- [x] T3.4 Project pending maintenance, last verified change, and recovery warnings into Home without direct Undo.

## Phase 4 — Activity & Recovery 2.0

- [x] T4.1 Add source/date/status/reboot filters, bounded search, and master-detail evidence sections.
- [x] T4.2 Add privacy-redacted JSON/Markdown selected-event export and fresh Action Center recovery handoff.

## Phase 5 — release and qualification

- [x] T5.1 Update active README, ROADMAP, ARCHITECTURE, CHANGELOG, user docs, completion, and man surfaces.
- [x] T5.2 Add release notes, direct-action audit, qualification report, and public evidence report.
- [x] T5.3 Run full rootless gates; keep physical/manual gates explicitly `unverified`.
- [x] T5.4 Publish through the tag-driven workflow and independently read back GitHub,
  assets, checksums, attestations, COPR, and wiki state.
