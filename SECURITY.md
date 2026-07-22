# Security Policy

## Supported Versions

| Version | Support |
|---|---|
| 17.x | Current stable security support |
| 16.x | Critical security fixes only |
| < 16 | End of life |

v18.0.0 "Haven" is under development and is not a supported release until its
release gates, tag, and public artifacts have been independently verified.

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
- GUI, CLI, daemon, automation, and agent entrypoints may create plans, but host
  changes require an explicit local Action Center confirmation.
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

The repository runs unit and integration tests, architecture and trust-boundary
checks, lint, type checking, Bandit, dependency audit, CodeQL, package builds,
and SBOM generation as release gates. A green unit suite alone is not sufficient
release evidence.

## Scope

In scope: privilege-boundary bypasses, command or argument injection, external
code execution, secret disclosure, API authentication/binding bypasses, unsafe
state restore, and Action Center confirmation bypasses.

Out of scope: attacks requiring physical access, social engineering, local
denial of service without a boundary bypass, and vulnerabilities wholly owned by
an upstream dependency (report those upstream as well).
