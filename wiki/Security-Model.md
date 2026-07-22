# Security Model

Haven treats Action Center as the only execution boundary for supported host
changes. GUI, CLI, daemon, automation, scheduler, and agent entry points use the
same classified definitions and verification rules.

## Operation classes

Every operation is one of:

| Class | Meaning |
| --- | --- |
| `host` | Changes the Fedora host and requires an Action Center plan plus explicit local confirmation |
| `app_state` | Changes Loofi-owned state only |
| `session` | Changes process- or session-scoped state |
| `manual_only` | Loofi can explain or prepare the operation but cannot execute it |

Unclassified mutation entry points fail the release gate. Background actors may
create plans but cannot confirm or execute host changes.

## Action Center lifecycle

The 56 first-party definitions declare their Fedora variants, reboot policy,
affected resources, closed parameters, preflight, preview, confirmation,
verification, and recovery policy.

1. Preflight captures the current system facts.
2. Planning validates parameters and creates a short-lived, digest-bound plan.
3. Apply repeats preflight and requires explicit local confirmation.
4. A cross-process lease permits one host mutation at a time.
5. Verification reads the resulting state independently. Exit status zero is
   not enough to mark a host change successful.
6. Interrupted work remains recorded and never resumes, retries, rolls back, or
   reboots automatically.

Unsupported host operations use `manual_only` plans. Reboot-requiring work can
pause at `awaiting_reboot`, but Loofi never triggers the reboot itself.

## Privileged commands

- Privileged commands use Polkit through `pkexec`, never `sudo`.
- Commands are argument vectors and never use `shell=True` or `sh -c`.
- Every subprocess call has an explicit timeout.
- Parameters use closed schemas and validation before command construction.
- Package operations select DNF or rpm-ostree through Fedora variant policy.
- UI modules do not execute subprocesses or contain domain logic.

Do not copy a rendered command from a plan into storage. Persisted commands are
never authoritative; the reviewed definition regenerates them at preview and
apply time.

## State integrity

Action Center plans and runs use schema v3. Writable v1 and v2 state migrates
atomically with a last-known-good backup and readback. Unknown future schemas
remain read-only.

State backup and restore reject path traversal, duplicate entries, oversized
data, unsupported schemas, and hash mismatches. Restore requires a generated
plan and can roll back already changed domains if a later domain fails.
Registered secret domains, raw logs, caches, and executable plugin code are not
included in default archives.

## External code and local profiles

Only application-owned providers from the reviewed package are importable.
Loofi does not discover or execute third-party Python extensions.

Existing legacy extension directories remain user-owned. The Local Profiles
view can inventory and export them but never loads or deletes their code. The
public Marketplace, reviews, analytics, updater, dependency resolver, and hot
reload are retired.

Local profiles use a closed, data-only schema. Imports reject symlinks, unsafe
paths, unknown fields, unsupported schemas, invalid values, and files larger
than 1 MiB. Accepted content becomes a reviewable plan before host settings
change.

## Secrets

Gist and JWT secrets use the desktop Secret Service through `keyring` when
persistent storage is available. A legacy plaintext value is removed only after
the persistent write is read back successfully.

If Secret Service is unavailable, a new secret remains in memory for the
current process. There is no plaintext file fallback. Other sensitive local
configuration uses atomic writes with private file permissions.

## Local Web API

- The optional API accepts loopback hosts only. A non-loopback
  `LOOFI_API_HOST` stops startup.
- Authenticated endpoints expose status and inspection data. There is no remote
  host-mutation endpoint.
- Token issuance is the only mutating HTTP operation and is rate-limited.
- API keys can be inspected, rotated, or revoked locally with `api-key` CLI
  commands.

Browser storage of an issued bearer token is scoped to the local Web UI. Treat
the token as a credential and revoke it if the browser profile is shared or
compromised.

## Privacy and audit data

Audit and support data redact credentials and token-like values. Support bundles
exclude raw command stdout and stderr, external extension code, and secret
domains. Paths, hostnames, email-like strings, and other identifying values are
redacted by the shared export boundary.

## Release gates

A public release requires the full suite, coverage, lint, typing, architecture,
state, statistics, documentation, Bandit, dependency, CodeQL, SBOM, RPM,
Flatpak, and source-distribution checks. It also requires physical Fedora 44
Traditional and Atomic validation and exact-commit publication readback.

Haven passed local tests, Bandit, dependency checks, package builds, canonical
CodeQL, exact-commit GitHub artifact verification, and a clean Fedora 44 COPR
installation. Historical Sentinel is preserved as
`legacy-v18.0.0-sentinel`.

## Reporting a vulnerability

Use a private
[GitHub Security Advisory](https://github.com/loofiboss-bit/loofi-fedora-tweaks/security/advisories/new).
Include the affected version, reproduction steps, impact, and any known
mitigation. Do not open a public issue for an unpatched vulnerability.

See the repository
[security policy](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/SECURITY.md)
for supported versions and scope.
