# Loofi Fedora Tweaks v25.0.0 “Proof” Plan

Status: v25.0.4 “Proof” release preparation; historical v25.0.0–v25.0.3 tags
remain preserved and v25.0.4 is the separate release identity.

## Objective

Make an eligible maintenance request follow one bounded path:

`request → Action Center plan → fresh preflight → optional compact confirmation → execute → independent verify → typed outcome`

Direct execution is a policy projection over the existing Action Center. It is not a second executor or a bypass around confirmation, leases, audit, expiry, interruption, recovery, or verification.

## Scope

1. Establish the v24 checkout baseline and version-lineage collision record.
2. Add canonical fail-closed eligibility derived from audited Action Center metadata.
3. Add versioned, atomic Safety & Execution settings with direct and review-first modes.
4. Add the PyQt-free `DirectActionService` and typed Outcome Evidence model.
5. Add the stable CLI `run ACTION_ID` workflow with dry-run, `--yes`, and JSON envelope.
6. Integrate high-traffic GUI routes, Home continuation state, and Activity & Recovery 2.0.
7. Update active documentation, completion/man surfaces, packaging metadata, and candidate release notes.
8. Run rootless/offscreen verification, publish v25.0.4 through the canonical
   workflow, and report physical/manual gates separately.

## Non-goals and hard boundaries

- No new top-level destination, QML surface, marketplace, cloud provider, telemetry, AI decision-maker, scheduler, unattended mode, automatic repair, retry, rollback, resume, reboot, or privileged daemon/API mutation path.
- No arbitrary shell or user-supplied command vector.
- No execution from preview or dry-run.
- Do not move, delete, or recreate historical v25.0.0–v25.0.3 tags. The
  release uses the first unused v25 patch identity, v25.0.4.
- Do not install packages, reboot, or mutate the real host as part of release
  publication; physical qualification remains a separate manual gate.

## Acceptance contract

- Unknown, incomplete, unsupported, manual-only, destructive/high-risk, unverifiable, or future-schema requests return a truthful review/blocked outcome.
- Low-risk eligible actions may execute directly only after fresh preflight; medium-risk actions require one compact confirmation when policy enables it.
- Every executed action has a durable Action Center plan/run, correlation ID, audit record, lease, independent verification attempt, and typed classification.
- GUI mutation remains asynchronous and non-concurrent; CLI and GUI use the same service and Action Center authority.
- Activity & Recovery never invents before/after facts and never exposes raw command vectors or secrets.
- Existing route IDs, persisted state, Action Center CLI compatibility, Traditional/Atomic behavior, API read-only behavior, and lazy loading remain intact.
