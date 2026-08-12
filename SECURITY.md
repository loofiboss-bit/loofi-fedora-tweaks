# Security Policy

## Supported Versions

| Version | Support |
|---|---|
| 25.x | Current public Proof release support |
| 24.x | Previous public release support |
| 23.x | Critical security fixes only |
| < 23 | End of life |

v25.0.4 "Proof" is the current public release; v24.0.0 "Flow" is the previous
public release. Historical v25.0.0–v25.0.3 tags are preserved without
modification, and v25.0.4 is the separate Proof release identity.

## Reporting a Vulnerability

Use a private [GitHub Security Advisory](https://github.com/loofiboss-bit/loofi-fedora-tweaks/security/advisories/new).
Include affected versions, reproduction steps, impact, and any suggested
mitigation. Do not open a public issue for an unpatched vulnerability.

## Current Security Boundaries

### Host mutations

- Privileged commands use Polkit (`pkexec`), never `sudo`.
- Commands use argument vectors, never `shell=True`, and subprocess calls have
  explicit timeouts.
- Action Center plans expire, are re-preflighted before execution, and never
  persist an authoritative command vector.
- Every operation is classified as `host`, `app_state`, `session`, or
  `manual_only`; unclassified mutations fail the release gate.
- GUI and CLI direct-action entrypoints may execute only through the bounded
  DirectActionService over Action Center. Host changes still require fresh
  preflight, policy-appropriate confirmation, a lease, and independent
  verification.
- Unknown, incomplete, manual-only, high-risk, unsupported, unverifiable, and
  future-schema requests fail closed to review or blocked outcomes.
- `--dry-run` and previews never execute. A successful command without an
  independent verifier is never presented as verified.
- Reboot, rollback, and distribution upgrade are never started automatically.

### Extensions and presets

- Only application-owned, built-in page providers are importable.
- External Python extension directories are not scanned or imported.
- Existing third-party files remain user-owned and are never deleted
  automatically. The Legacy Extensions view can inventory and export them.
- The public Marketplace, reviews, analytics, updater, dependency resolver, and
  executable preset distribution are retired.
- Local preset files are data only. They must pass schema and path validation
  and become reviewable plans before any host change.

### Outcome and activity evidence

- Outcome Evidence records expected, execution, verification, reboot, resource,
  recovery, and source-quality facts without treating exit code zero as proof.
- Activity & Recovery exports are bounded and redacted; executable vectors,
  raw output, credentials, and secret-shaped fields are excluded.
- Home links to Activity & Recovery for recovery review and does not provide a
  direct Undo operation for Proof runs.

### Secrets and state

- Gist tokens and JWT signing secrets use Secret Service through `keyring`.
- Legacy plaintext secrets are removed only after a persistent readback succeeds.
- If Secret Service is unavailable, secrets remain in memory for the current
  process; there is no plaintext file fallback.
- API key hashes and other sensitive configuration use atomic writes with mode
  `0600`.
- State restore rejects path traversal, duplicate entries, unsupported schemas,
  oversized data, and hash mismatches.

### Local Web API

- The optional API accepts only loopback hosts. A non-loopback
  `LOOFI_API_HOST` stops startup.
- The API is read-only except for token issuance.
- Token issuance is rate-limited. API keys can be rotated or revoked locally.
- Authenticated `GET` routes expose status and inspection data; there is no
  remote mutation endpoint.

## Security Testing

The repository requires unit and integration tests, architecture and
trust-boundary checks, lint, type checking, Bandit, dependency audit, CodeQL,
package builds, and SBOM generation as release gates. Flow passed its public
gates; Proof is public, but physical-host, installation, and reboot evidence
remain separate and a green rootless suite alone is not physical qualification.

## Scope

In scope: privilege-boundary bypasses, command or argument injection, external
code execution, secret disclosure, API authentication/binding bypasses, unsafe
state restore, and Action Center confirmation bypasses.

Out of scope: attacks requiring physical access, social engineering, local
denial of service without a boundary bypass, and vulnerabilities wholly owned by
an upstream dependency (report those upstream as well).
