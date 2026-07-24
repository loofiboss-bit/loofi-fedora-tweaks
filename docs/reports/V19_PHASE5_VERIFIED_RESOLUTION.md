# v19 Phase 5 — Verified Resolution and Support Evidence

**Status:** Complete  
**Date:** 2026-07-24  
**Scope:** Read-only before/after outcomes, follow-up UX, support evidence, and API/CLI parity

## Outcome

Loofi now keeps Action Center verification and System Check resolution as two
separate, inspectable facts:

- `verified` means the trusted action-specific verifier succeeded;
- `resolved` means the original finding is absent from a later compatible
  System Check whose relevant source completed after verification.

A linked run waiting for reboot remains pending. Exit code zero, successful
execution, and successful verification do not independently mark a finding
resolved.

## Comparison contract

`core/system_check/comparison.py` reconstructs supported schema-v1 results from
the existing JSON health timeline without migration or rewrite. Two results
are compatible only when they have:

- the same closed profile;
- the same Traditional or Atomic host variant;
- distinct IDs and increasing completion timestamps;
- usable follow-up evidence for each finding source.

Each original finding is deterministically classified as:

- `resolved`: absent after its source completed;
- `unchanged`: the same stable finding/resource remains without stronger
  severity or evidence;
- `worsened`: severity, known state, or a direction-aware numeric signal
  increased;
- `not_comparable`: profile, variant, order, source availability, or identity
  is insufficient.

Completed legacy schema-v1 results without `completed_sources` remain readable
and comparable only when the whole follow-up check completed without source
errors. Unknown future result schemas are skipped without mutation.

## User journey

- System Check History shows the latest comparison counts and individual
  finding outcomes.
- Linked maintenance cards show Action Center verification separately from the
  finding follow-up.
- After a linked run reaches `succeeded`, Action Center offers **Check again**
  for the affected resources and routes to the existing explicit Home check.
- `awaiting_reboot` keeps Check again unavailable until reboot-aware
  verification finishes.
- Home recommends a follow-up check when verified linked work has no later
  comparable result. A later resolved result removes the stale finding instead
  of retaining it as current.

## Support and API evidence

The canonical writer advances to Support Bundle v11. It preserves v10 fields
and adds:

- at most two supported System Check results;
- at most 50 findings and 10 source errors per result;
- one latest comparison;
- at most 25 linked plan/run metadata records.

Recursive redaction covers personal home paths, hostnames, emails, secret
values and keys, IPv4/IPv6 addresses, MAC addresses, and verifier messages.
Raw stdout, stderr, and command vectors are not added.

Authenticated `GET /api/system-check/latest` returns only the latest bounded,
privacy-safe saved result. It performs no collection. The loopback-only server
and token boundary are unchanged, and no System Check confirmation or execution
endpoint exists. `health comparison` provides the same versioned read-only
outcome through the CLI.

## Protected contracts

- Existing JSON snapshots and SQLite metrics are read in place.
- Action Center plan/run schema remains v4; no Phase 5 migration was added.
- One action, one lease, fresh preflight, explicit confirmation, independent
  verification, and no automatic reboot/retry/rollback remain unchanged.
- Stable routes and the explicit Home startup contract remain unchanged.
- Traditional and Atomic comparisons fail closed across a variant mismatch.
- The PyQt-free `core.system_check` package import remains intact through lazy
  compatibility exports.

## Verification

Phase-specific gates:

```text
just test-file test_system_check_comparison
just test-file test_support_bundle_system_check
just test-file test_api_system_check
just test-file test_home_service
just test-file test_observability_privacy
just test-file test_api_security
just lint
just typecheck
```

Results:

- comparison: 7 passed, 3 subtests;
- support evidence: 2 passed, 5 subtests;
- System Check API: 3 passed;
- Home: 18 passed;
- privacy: 2 passed, 7 subtests;
- API security: 3 passed, 6 subtests;
- lint and mypy: passed; mypy emitted only the established unchecked-body
  notes.

Supplemental compatibility evidence:

```text
just test-file test_system_check_models
just test-file test_system_check_action_handoff
just test-file test_cli_system_check
just test-file test_system_check_ui
just test-file test_maintenance_tab
just test-file test_main_window
just test-file test_action_center_assurance
just test-file test_action_center_v14
just test-file test_action_center_migrations
just test-file test_action_center_steward
just test-file test_api_server
just test-file test_api_action_center
just test-file test_support_bundle_v10
just test-file test_observability_redaction
just test-file test_startup_benchmark
PYTHONPATH=loofi-fedora-tweaks python scripts/validate_product_contract.py
PYTHONPATH=loofi-fedora-tweaks python scripts/validate_architecture.py
PYTHONPATH=loofi-fedora-tweaks python scripts/validate_v18_architecture.py
PYTHONPATH=loofi-fedora-tweaks python scripts/validate_v18_haven.py
just validate-release
just stats-check
git diff --check
```

All listed checks passed. Maintenance retained its 21 established conditional
legacy skips. The startup check remained green. During verification, the
PyQt-free import test exposed an eager type/store import and the architecture
gate exposed CLI module growth; both root causes were removed and their exact
gates passed on rerun.

## Remaining risk and deferred work

- Phase 6 owns real KDE accessibility, responsive rendering, screenshot,
  physical Traditional, exact Atomic deployment/reboot, security, packaging,
  coverage, and release-readiness certification.
- Comparison intentionally does not infer improvement from arbitrary
  free-form evidence. A still-present finding is `unchanged` unless a closed
  severity/state/numeric signal proves worsening.
- No version bump, commit, tag, push, release, or publication was performed.

## Proposed checkpoint

```text
feat(system-check): show verified before-and-after outcomes
```
