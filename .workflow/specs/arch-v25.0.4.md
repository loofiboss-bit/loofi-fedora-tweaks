# Architecture — v25.0.4 “Proof”

Status: public Proof release architecture. This document extends the v24 Flow
Action Center architecture and does not create another host-mutation authority.

## Flow

```text
GUI or CLI request
        ↓
DirectActionService (PyQt-free policy adapter)
        ↓
canonical ActionCatalog metadata audit
        ↓
ActionCenterOrchestrator.plan()
        ↓
fresh preflight + eligibility + settings policy
        ↓
optional compact confirmation
        ↓
ActionCenterOrchestrator.apply()
        ↓
independent Action Center verification
        ↓
OutcomeEvidenceComposer + Change Journal + Home projection
```

`ActionCenterOrchestrator` and `CommandFacade` remain the only execution path.
Direct mode chooses when the existing path may be entered; it never renders or
executes arbitrary commands itself.

## Canonical boundaries

- `core/actions/eligibility.py` derives direct/confirmation/review/blocked
  classification from `ActionDefinition` metadata and callable completeness.
- `core/actions/direct.py` validates registered IDs and typed parameters, creates
  a normal plan, invokes fresh preflight, delegates apply/verify, and returns a
  bounded typed result.
- `core/actions/outcomes.py` composes expected, execution, verification,
  reboot, recovery, resource, source-quality, and exact classification evidence.
- `core/settings/execution.py` owns versioned XDG Safety & Execution state;
  future schemas are read-only and force review-first behavior.
- `core/change_journal/*` provides bounded read-only filters/search and
  privacy-redacted selected-event export.
- GUI tabs remain PyQt presentation plus asynchronous workers; they contain no
  subprocess or domain mutation logic.
- CLI parsing and service dispatch accept only registered action IDs and typed
  parameters; shell command vectors are never accepted.

## Policy matrix

| Condition | Result |
| --- | --- |
| Complete low-risk metadata, supported target, fresh preflight allowed | Direct execution when mode/policy permit |
| Complete medium-risk metadata, supported target, fresh preflight allowed | One compact confirmation when enabled; otherwise review-first |
| High/destructive/manual-only/unverifiable/unknown/incomplete/future schema | Review required or blocked; never direct |
| Dry-run or preview | Plan and exact preview only; never execute |
| Successful command without independent verification | Unverified/partially verified; never “verified” |
| Verification requests reboot | Awaiting reboot; no automatic reboot |

## Persistence, privacy, and compatibility

New durable state uses existing XDG atomic-write and lock conventions. Outcome
and journal payloads are bounded and redact through existing privacy helpers;
command vectors, raw output, credentials, paths, and personal data do not enter
Activity & Recovery exports.

The six standard destinations, stable route IDs, lazy loading, Action Center
CLI, daemon/API read-only contracts, Traditional/Atomic package policy,
packaging manifest, and existing v24 state schemas remain compatibility gates.
Physical Wayland, input, accessibility, Polkit, reboot, and fresh Atomic gates
remain separate manual evidence.
