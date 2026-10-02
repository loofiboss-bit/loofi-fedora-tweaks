# State Integrity and Recovery

Loofi Fedora Tweaks v31.0.0 "Mastery" retains application-owned state under the
user's standard XDG config, data, cache, and runtime directories. Physical desktop validation remains unverified. State is separate from the Fedora deployment
and is preserved when the RPM is removed.

## State Doctor

Open **Health → System Check** to collect the state-integrity findings, or use
the corresponding diagnostic command:

```bash
loofi-fedora-tweaks --cli --json check
```

The separate `doctor` command inspects system dependencies, Fedora support,
and Polkit availability; it does not run the application-state validator.

State Doctor checks registered paths, permissions, JSON/JSONL readability,
SQLite integrity, stale locks, and recovery availability without changing
files. It reports incomplete or unavailable sources instead of repairing them
silently.

## Durable state rules

- JSON and JSONL writes use a same-directory temporary file, `fsync`, atomic
  replacement, directory `fsync`, private permissions, and readback.
- A bounded last-known-good copy is retained where the state domain supports
  recovery.
- Concurrent GUI and CLI access uses advisory locks with bounded timeouts and
  a typed busy result.
- Unsupported future schemas are read-only and are never overwritten.
- Migrations retain the original input and record completion only after verified
  readback.
- Numeric metrics and structured snapshots remain separate schemas; support
  export does not rewrite either store.

## Preserved domains

The application preserves system checks, update snapshots, internal plans and
runs, activity history, and backup metadata. Specialist or retired feature
data is not imported into the v29 product surface. Package removal and the
repository uninstaller do not delete user state.

## Action plans and recovery

Action plans persist a registered action ID and validated parameters, not an
authoritative command supplied by a file or user. Before execution the current
definition regenerates the command and performs fresh preflight. A single
cross-process lease prevents concurrent mutations. Interrupted, failed, and
restart-required runs remain inspectable and require explicit follow-up.

If recovery is unavailable, the plan says so before authorization. Loofi never
creates an automatic rollback, restarts the host, retries a failed operation,
or resumes an interrupted run.

## Archives and privacy

Support and recovery archives are bounded and reject path traversal, duplicate
entries, oversized content, unsupported schemas, missing content, and digest
mismatches. Diagnostic exports redact secrets, credentials, personal paths,
hostnames, network identifiers, and raw process output. Review an archive
before sharing it.

## Atomic and traditional deployments

The runtime records the deployment backend explicitly. Traditional Fedora and
Atomic Fedora use different package and restart semantics. An operation is
shown only when its capability, authorization, verification, and recovery
contract is known. Unknown or bootc backends remain unavailable rather than
falling back to a traditional assumption.

Some Atomic changes require a staged deployment and a restart through the
normal Fedora workflow. Verification is a separate explicit step after the
new deployment is booted; Loofi does not restart the machine itself.

## If state is damaged

1. Stop any second package or maintenance transaction.
2. Run Health → System Check (or `loofi-fedora-tweaks --cli --json check`)
   and save the state-integrity findings and source errors.
3. Preserve the original files and last-known-good copy.
4. Create a support bundle and review it before sharing.
5. Follow the domain-specific recovery guidance shown by System Check.

Plan saving and migration refuse malformed JSON, invalid documents, and
invalid records. Neither the original `action_plans.json` nor its `.lkg` backup
is replaced on that refusal. Preserve both files and inspect a copy before
explicit recovery; a new save is not a repair. If a source cannot be loaded,
System Check reports it as unavailable rather than treating it as empty.

Never delete a corrupt input before a recovery copy exists. Report the exact
state domain, schema, version, and reproduction steps in the issue tracker.

## Tweak restoration evidence

Comfort captures versioned tweak identity and exact before/after values in
`verification_result.data`, without changing the outer schema-v4 format or
atomic persistence. Restoration accepts only a source run ID and resolves
values from verified history; caller-supplied settings cannot override it.
Fresh preflight blocks external drift, later attempts, already consumed
restores, unavailable choices, and missing or legacy evidence. History pruning
can remove eligibility. A restore is a new verified run, never an automatic
rollback; durable acknowledgement failure cannot be shown as saved success.

A persisted running or verifying run reserves the mutation boundary, including
when execution acknowledgement cannot be saved. Activity & Recovery must resolve
that run before another mutation starts. Malformed history blocks writes and
startup migration; no unreadable record is silently dropped or overwritten.
Stored creation order, rather than wall-clock timestamps or result updates,
determines the latest attempt. Execution and verification success must both be
boolean true. Custom numeric writes are additionally limited at the executor
boundary to the matching Action Center restore action; legacy callers and
ordinary set actions cannot submit them.
