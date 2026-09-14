# State Integrity and Recovery

Loofi Fedora Tweaks v28.0.2 "Ease" keeps application-owned state under the
user's standard XDG config, data, cache, and runtime directories. State is
separate from the Fedora deployment and is preserved when the RPM is removed.

## State Doctor

Run the read-only diagnostic command:

```bash
loofi-fedora-tweaks --cli doctor
```

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

The application preserves system checks, update snapshots, Action Center plans
and runs, activity history, and backup metadata. Specialist or retired feature
data is not imported into the v28 product surface. Package removal and the
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
2. Run `loofi-fedora-tweaks --cli doctor` and save its output.
3. Preserve the original files and last-known-good copy.
4. Create a support bundle and review it before sharing.
5. Follow the domain-specific recovery guidance shown by the doctor.

Never delete a corrupt input before a recovery copy exists. Report the exact
state domain, schema, version, and reproduction steps in the issue tracker.
