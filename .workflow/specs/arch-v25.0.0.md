# Architecture — v25.0.0 “Proof” (Superseded Candidate)

Status: superseded by the published v25.0.4 “Proof” release. This historical
planning snapshot extends the v24 Action Center architecture and does not
define another host-mutation authority.

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
independent ActionCenter verification
        ↓
OutcomeEvidenceComposer + Change Journal + Home projection
```

`ActionCenterOrchestrator` and `CommandFacade` remain the only execution path. Direct mode chooses when the existing path may be entered; it never renders or executes arbitrary commands itself.

## Canonical boundaries

- `core/actions/eligibility.py`: derives direct/confirmation/review/blocked classification from `ActionDefinition` metadata and callable completeness. It must fail closed.
- `core/actions/direct.py`: validates registered action IDs and typed parameters, creates a normal plan, invokes fresh preflight, applies policy, delegates run/verify, and returns a bounded typed result.
- `core/actions/outcomes.py`: composes expected, execution, verification, resource, reboot, recovery, source/freshness, and exact classification evidence without inference.
- `core/settings/execution.py`: versioned XDG state for Direct/Review first and safety toggles; future schemas are read-only and force review-first behavior.
- `core/change_journal/*`: read-only source composition, bounded filters/search, and privacy-redacted selected-event export.
- GUI tabs: PyQt presentation and asynchronous workers only. No subprocess or domain mutation logic.
- CLI: parser and service dispatch only. `run` accepts registered IDs and typed `--param key=value`; it never accepts a shell command.

## Policy matrix

| Condition | Result |
| --- | --- |
| Complete low-risk metadata, supported target, fresh preflight allowed | Direct execution when mode/policy permit |
| Complete medium-risk metadata, supported target, fresh preflight allowed | One compact confirmation when enabled; otherwise review-first |
| High/destructive/manual-only/unverifiable/unknown/incomplete/future schema | Review required or blocked; never direct |
| Dry-run or preview | Plan and exact preview only; never execute |
| Successful command without independent verification | Unverified/partially verified; never “verified” |
| Verification requests reboot | Awaiting reboot; no automatic reboot |

## Persistence and privacy

All new durable state uses the existing XDG state/atomic-write/lock conventions. Future schema data is read-only. Outcome and journal payloads are bounded and redact through the existing privacy helpers; command vectors, raw output, credentials, paths, and personal data do not enter Activity & Recovery exports.

## Compatibility gates

The six standard destinations, stable route IDs, lazy loading, Action Center CLI, daemon/API read-only contracts, Traditional/Atomic package-manager policy, packaging manifest, and existing v24 state schemas remain compatibility gates. Physical Wayland, input, accessibility, Polkit, reboot, and fresh Atomic gates remain separate manual evidence.
