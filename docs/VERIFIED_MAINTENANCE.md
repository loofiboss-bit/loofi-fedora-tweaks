# Verified Maintenance

v15.0.0 "Essentials" preserves the complete v14 verified-maintenance contract
while simplifying where it appears. Fedora 44 is the supported target; Fedora
45 remains preview/advisory.

## Action Center workflow

Open **Software & Updates → Maintenance → Action Center**. Select a supported
action, create a plan, and review its preflight decision, exact command,
privilege boundary, risk, expiry, and rollback guidance. Applying a plan always
requires explicit confirmation. Medium-risk actions without supported rollback
also require acknowledgement of that limitation.

The lifecycle is:

```text
planned → ready → running → verifying → succeeded
                ↘ failed / verification_failed / interrupted
```

`succeeded` means the action-specific verifier passed; exit code zero alone is
not sufficient. If the application exits during a run, the run is preserved as
`interrupted` and is never resumed automatically.

## CLI

```bash
loofi action-center list
loofi action-center plan dnf-clean-all
loofi action-center show PLAN_ID
loofi action-center apply PLAN_ID --confirm
loofi action-center plan restart-failed-service --service example.service
loofi action-center apply PLAN_ID --confirm --accept-no-rollback
loofi action-center verify RUN_ID
loofi action-center history
```

Use the global `--json` flag before the command for stable machine-readable
plan, policy, run, and verification envelopes.

## Executable catalog

| Action | Policy | Verification |
| --- | --- | --- |
| `dnf-clean-all` | Traditional Fedora only; Atomic remains read-only/manual | Fresh package/repository health check |
| `restart-failed-service` | Unit must be present in a fresh failed-unit list | Unit is active and no longer failed |
| `fstrim-all` | Requires discard support and the `fstrim` binary | Successful per-filesystem trim result |

All other recommendations remain manual-only. Essentials does not provide fix-all,
scheduled repair, automatic rollback, automatic retry, remote API apply, or
plugin/AI-provided executable actions.

## Recovery and support

Plans expire after 30 minutes and are re-preflighted before execution. Only one
Action Center mutation can run across GUI and CLI processes. The read-only API
can inspect plans and runs, and Support Bundle v10 exports redacted lifecycle
evidence linked by run ID without raw command output or secrets.

Home and global search may show attention or action entry points, but activation
only opens `maintenance:action-center`. They never create, apply, verify, retry,
or resume a plan. Standard and Advanced mode use the same safety policy.
