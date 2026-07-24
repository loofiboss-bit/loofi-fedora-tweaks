# v19 Phase 4 — Finding-to-Action Center Handoff

**Status:** Complete  
**Date:** 2026-07-24  
**Scope:** Validated finding handoff and optional Action Center context

## Outcome

A current, fresh System Check finding can now expose **Review safe action** only
when its closed evidence resolves to one existing first-party Action Center
definition. Activating the control opens Action Center with that exact action
preselected. It does not create a plan, render a command, confirm, or execute.

When the user later chooses **Review & Plan**, Action Center independently:

1. rereads the newest persisted System Check;
2. resolves the exact check ID and finding fingerprint;
3. reconstructs and validates the finding and its evidence fingerprint;
4. rejects stale, unknown, duplicate, malformed, variant-mismatched, or
   mapping-mismatched context;
5. derives the action and closed parameters from the static mapping;
6. runs the existing parameter policy, command renderer, host/variant policy,
   and fresh preflight.

No command, arbitrary parameter, callback, or execution authority crosses the
System Check boundary.

## Schema decision

Action Center plan and run stores advance from schema v3 to schema v4 because
the required relationship must survive plan/run persistence. Optional
`FindingContext` contains only:

- check result ID;
- finding fingerprint;
- independent evidence digest;
- origin route;
- affected resources.

Context-bearing plans include this context in their integrity digest, so
tampering blocks preparation. The context is not an input to action lookup,
parameter policy, command rendering, preflight, confirmation, no-rollback
acknowledgement, execution, verification, or mutation leasing.

Writable v1-v3 plans and runs migrate atomically to v4 with the established
same-directory replace, last-known-good backup, and readback behavior. Unknown
future schemas remain unmodified and read-only. Context-free plans retain the
v18 digest calculation and behavior.

## Trust-boundary results

| Requirement | Evidence |
| --- | --- |
| Exact audited action | Action ID and parameters are reconstructed from the latest persisted finding |
| No finding-supplied command | UI emits only check ID, fingerprint, and origin route |
| Tampered context blocked | Finding evidence integrity and plan digest are both validated |
| Stale context blocked | Only the newest persisted terminal check and fresh evidence are accepted |
| Manual-only stays manual | Guidance and reason are shown; no Review safe action button exists |
| Fresh preflight retained | Action Center renders and preflights during planning and again before execution |
| Explicit confirmation retained | `prepare_run(..., confirmed=True)` remains the only interactive transition |
| No-rollback acknowledgement retained | Existing medium/high-risk check is unchanged |
| One action and one lease | Existing plan shape and cross-process mutation lease are unchanged |
| Background/agent safety | Daemon helpers remain plan-only and cannot confirm or run |
| Traditional/Atomic policy | Resolver checks the persisted host variant and Action Center rechecks live variant policy |

## Verification

Phase-specific checks:

```text
just test-file test_system_check_action_handoff
just test-file test_action_center_steward
just test-file test_action_center_migrations
just test-file test_action_center_assurance
just test-file test_action_center_v14
PYTHONPATH=loofi-fedora-tweaks python scripts/validate_product_contract.py
just lint
just typecheck
```

Supplemental compatibility gates:

```text
just test-file test_maintenance_tab
just test-file test_main_window
just test-file test_v15_phase6_ui
just test-file test_haven_contracts
just test-file test_system_check_service
just test-file test_startup_benchmark
PYTHONPATH=loofi-fedora-tweaks python scripts/validate_architecture.py
PYTHONPATH=loofi-fedora-tweaks python scripts/validate_v18_architecture.py
PYTHONPATH=loofi-fedora-tweaks python scripts/validate_v18_haven.py
```

All listed checks passed. The 21 skipped Maintenance tests are the established
conditional legacy branches; all executed Action Center and handoff tests
passed.

## Remaining risk and deferred work

- Phase 5 owns comparison of later checks and must keep Action Center
  `verified` separate from finding `resolved`.
- Linked metadata is displayed on the current plan/run detail surfaces; richer
  historical comparison and support-bundle export remain Phase 5 work.
- Real KDE accessibility, screenshot, physical Traditional, and exact Atomic
  deployment certification remain Phase 6 work.
- No version bump, commit, tag, push, release, or publication was performed.

## Proposed checkpoint

```text
feat(actions): link findings to reviewed maintenance plans
```
