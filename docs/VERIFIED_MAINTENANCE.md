# Verified Maintenance

v18.0.0 "Haven" makes Action Center the trust boundary for supported host
changes across GUI, CLI, daemon, automation, scheduler, and agent entry points.
Its 56 first-party definitions declare operation class, Fedora variants, reboot
policy, affected resources, preflight, confirmation, verification, and recovery
policy. Fedora 44 is the supported target; Fedora 45 remains preview-only.

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

All other recommendations remain manual-only. Haven does not provide fix-all,
scheduled repair, automatic rollback, automatic retry, remote API apply, or
plugin/AI-provided executable actions.

## Recovery and support

Plans expire after 30 minutes and are re-preflighted before execution. Each
plan contains one action and validated parameters; the reviewed definition
regenerates the command, so persisted commands are never authoritative. Only one
Action Center mutation can run across GUI and CLI processes. The read-only API
can inspect plans and runs. Support Bundle v11 preserves the v10 lifecycle
evidence and adds bounded System Check results, comparison outcomes, and linked
finding metadata without raw command output or secrets.

Action Center `verified` means the action-specific verifier passed.
System Check `resolved` means the original finding is absent from a later
compatible check whose source completed. These facts are intentionally
separate. A successful linked run offers **Check again**; a run waiting for
reboot stays pending until reboot-aware verification finishes, and missing
follow-up sources produce `not_comparable`, never `resolved`.

Writable schema-v1 through schema-v3 plans and runs migrate atomically to
schema v4 with a last-known-good backup and readback. Schema v4 can link a plan
and run to a validated System Check finding, but that context cannot alter the
action, command, policy, or confirmation. Unknown future schemas remain
read-only. Home and global search may show attention or action entry points, but
activation only opens `maintenance:action-center`. They never apply, verify,
retry, or resume a plan. Standard and Advanced mode use the same safety policy.
