# Verified Maintenance

v17.0.0 "Assurance" extends the v14 verified-maintenance contract from three
maintenance actions to the five canonical product workflows. Fedora 44 is the
supported target; Fedora 45 remains preview/advisory. This document describes
the released v17 contract and its supported manual boundaries.

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
                                  ↕
                          awaiting_reboot
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
loofi action-center plan install-application --source flatpak --package-id org.mozilla.firefox
loofi action-center plan vacuum-journal --days 14
loofi action-center plan create-recovery-point --backend snapper --description "Before update"
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
| `update-fedora-system` | Exact Traditional NEVRAs or one Atomic staged deployment | RPM health and exact packages, or booted deployment after reboot |
| `update-flatpaks` | Exact refs and target commits | Only planned refs match their target commits |
| `update-firmware` | Exact device GUID, version, and checksum | fwupd history, with explicit reboot hand-off |
| `install-application` / `remove-application` | One Fedora package or Flatpak ref | Exact RPM identity, Atomic deployment, or Flatpak commit/state |
| `vacuum-journal` | Retention is exactly 7, 14, or 30 days | Fresh usage is measured and does not increase |
| `autoremove-packages` | Exact preflight package list; Traditional only | Every planned package is absent and package health passes |
| `create-recovery-point` | Timeshift or Snapper and printable description | A new listed snapshot contains the description |

All other recommendations remain manual-only. Assurance does not provide fix-all,
scheduled repair, automatic rollback, automatic retry, remote API apply, or
plugin/AI-provided executable actions.

## Recovery and support

Plans expire after 30 minutes and are re-preflighted before execution. Each
plan contains one action and one command vector. Only one
Action Center mutation can run across GUI and CLI processes. The read-only API
can inspect plans and runs, and Support Bundle v10 exports redacted lifecycle
evidence linked by run ID without raw command output or secrets.

Schema-v1 plans and runs migrate atomically to v2 with a last-known-good backup
and readback. Future schemas are never rewritten. Home and global search may show attention or action entry points, but activation
only opens `maintenance:action-center`. They never create, apply, verify, retry,
or resume a plan. Standard and Advanced mode use the same safety policy.
