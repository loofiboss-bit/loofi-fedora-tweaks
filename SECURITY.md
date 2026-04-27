# Security Policy

<!-- markdownlint-configure-file {"MD060": false} -->

## Supported Versions

| Version | Supported                             |
| ------- | ------------------------------------- |
| v3.x    | Active                                |
| v2.x    | Legacy / no guaranteed security fixes |
| < v2    | End of life                           |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability in Loofi Fedora Tweaks, please report it responsibly.

### How to Report

1. **GitHub Security Advisories (preferred)**: [Create a private security advisory](https://github.com/multidraxter-bit/loofi-fedora-tweaks/security/advisories/new)
2. **Email**: security@loofi.dev (if available)

### What to Include

- Description of the vulnerability
- Steps to reproduce
- Affected version(s)
- Potential impact assessment
- Any suggested fixes (optional)

### What to Expect

| Timeline | Action                                          |
| -------- | ----------------------------------------------- |
| 48 hours | Acknowledgment of your report                   |
| 7 days   | Initial assessment and severity classification |
| 30 days  | Fix developed and tested                       |
| 90 days  | Public disclosure (coordinated with reporter)  |

We follow a **90-day responsible disclosure timeline**. If a fix takes longer, we will communicate the timeline and provide interim mitigations.

## Security Architecture

### Privilege Escalation

- All privileged operations use **Polkit (`pkexec`)** — never `sudo`
- Granular Polkit policies per capability (firewall, network, storage, etc.)
- `PrivilegedCommand` builder validates parameters before execution
- All privileged actions are audit-logged to `~/.config/loofi-fedora-tweaks/audit.jsonl`

### Subprocess Safety

- All `subprocess.run()` and `subprocess.check_output()` calls include `timeout` parameter
- No shell string interpolation — commands use argument lists
- `CommandRunner` wraps `QProcess` for async GUI operations

### Data Handling

- No telemetry or data collection
- Configuration stored locally at `~/.config/loofi-fedora-tweaks/`
- Plugin sandbox restricts file system and network access
- API server binds to localhost by default (requires `--unsafe-expose` for network binding)
- Safe Mode defaults to enabled for API mutations and must be explicitly disabled before write actions are allowed
- Plugin auto-update defaults to off and only installs updates after explicit user opt-in

### Dependencies

- Minimal dependency footprint (PyQt6, standard library)
- Dependabot monitors for vulnerable dependencies
- CI runs Bandit, pip-audit, and Trivy on every PR

## API Threat Model

The optional REST API server (`--api` mode) exposes system operations over HTTP. It is designed for local automation and must never be exposed to untrusted networks.

### Binding & Network Exposure

| Setting           | Binding                                 | Risk Level                  |
| ----------------- | --------------------------------------- | --------------------------- |
| Default           | `127.0.0.1:8000` / `localhost` / `::1` | Low — loopback only         |
| `--unsafe-expose` | `0.0.0.0:8000`                         | **High** — network-accessible |

The `--unsafe-expose` flag is required for any non-loopback bind and the server refuses startup without it.

### Authentication & Bootstrap

- **JWT HS256** tokens with 3600s (1 hour) lifetime
- **bcrypt** hashed API keys stored in `~/.config/loofi-fedora-tweaks/api_auth.json`
- Stored auth data must use owner-only permissions on POSIX hosts; invalid or world-readable auth files are rejected
- `POST /api/key` is only unauthenticated during first-run bootstrap; once an API key exists, Bearer JWT auth is required for rotation
- `POST /api/token` returns `409` until bootstrap provisions the first API key
- Bearer token required on all endpoints except `GET /api/health`
- No token revocation (tokens expire naturally)

### Route Policies & Rate Limiting

The API enforces route-aware token bucket limits and emits `Retry-After` plus `X-Loofi-Route-Policy` headers.

| Policy Bucket | Typical Routes                                              | Purpose                        |
| ------------- | ----------------------------------------------------------- | ------------------------------ |
| `public`      | `GET /api/health`                                           | Unauthenticated health probe   |
| `auth`        | `POST /api/key`, `POST /api/token`                          | Bootstrap and token issuance   |
| `read`        | `GET /api/info`, `GET /api/agents`, profile export/list routes | Authenticated read-only access |
| `mutation`    | `POST /api/execute`, profile apply/import routes            | State-changing operations      |

### Endpoint Security

| Endpoint                         | Auth                              | Risk       | Mitigations                                                                 |
| -------------------------------- | --------------------------------- | ---------- | --------------------------------------------------------------------------- |
| `GET /api/health`                | None                              | Minimal    | Returns `{"status": "ok"}` only, no version leak, `public` rate-policy header |
| `POST /api/key`                  | None during bootstrap, then Bearer JWT | High       | Bootstrap-only unauthenticated path, owner-only auth storage, `auth` rate limiting |
| `POST /api/token`                | API key                           | Medium     | Requires bootstrap first, rejects unsafe/invalid auth storage, `auth` rate limiting |
| `GET /api/info`, `GET /api/agents` | Bearer JWT                      | Low        | Read-only data, `read` rate limiting                                        |
| `GET /api/profiles*` exports/lists | Bearer JWT                      | Low        | Read-only data, `read` rate limiting                                        |
| `POST /api/profiles*` apply/import | Bearer JWT                      | Medium     | Mutation rate limiting, structured validation                               |
| `POST /api/execute`              | Bearer JWT                        | **Critical** | Command allowlist, audit logging, Safe Mode mutation guard, parameter validation |

### Mutation Guardrails

- Safe Mode is enabled by default and blocks mutating `POST /api/execute` requests until the user disables it in **Settings → Behavior**
- Preview execution remains available while Safe Mode is enabled
- Dangerous local operations route through the shared confirmation dialog with registry-backed risk badges and revert hints

### Command Allowlist (`POST /execute`)

The executor enforces a `COMMAND_ALLOWLIST` frozenset. Only executables listed in the allowlist (derived from `PrivilegedCommand` builders + read-only diagnostics) can be invoked. Disallowed commands return HTTP 403 with an audit log entry.

Allowlisted categories:

- **Package management**: `dnf`, `rpm-ostree`, `flatpak`, `rpm`
- **System services**: `systemctl`, `journalctl`, `loginctl`, `hostnamectl`, `timedatectl`
- **Hardware/firmware**: `fwupdmgr`, `fstrim`, `lsblk`, `lspci`, `lsusb`, `lscpu`, `sensors`
- **Network**: `nmcli`, `firewall-cmd`, `ip`, `ss`, `resolvectl`
- **Privilege**: `pkexec` (Polkit escalation)
- **Diagnostics**: `uname`, `cat`, `grep`, `free`, `df`, `findmnt`, `sysctl`

### Plugin Update Safety

- `plugin_auto_update` is a first-class persisted setting and defaults to `false`
- Daemon update checks do not auto-install plugin updates unless the setting is explicitly enabled
- Plugin updates continue to use checksum verification and installer rollback/backup behavior on failure

### Known Limitations

- No token revocation mechanism (1-hour expiry is the only control)
- No TLS by default (acceptable for localhost; not for `--unsafe-expose`)

### Recommendations for Operators

1. **Never** use `--unsafe-expose` on machines accessible from untrusted networks
2. Keep Safe Mode enabled unless you intentionally need remote mutation workflows
3. Rotate API keys periodically via `AuthManager.generate_api_key()`
4. Monitor `audit.jsonl` for unexpected command or bootstrap patterns
5. Consider a reverse proxy with TLS if remote access is required

## Scope

The following are **in scope** for security reports:

- Privilege escalation beyond intended Polkit policies
- Command injection via parameter validation bypass
- Unauthorized file access or modification
- Plugin sandbox escape
- API authentication bypass
- Information disclosure of sensitive system data

The following are **out of scope**:

- Attacks requiring physical access to the machine
- Social engineering
- Denial of service against local-only services
- Issues in upstream dependencies (report to upstream maintainers)

## Security Updates

Security fixes are released as patch versions (e.g., v35.0.1) and announced via:

- GitHub Releases
- CHANGELOG.md
- GitHub Security Advisories
