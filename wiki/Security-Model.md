# Security & Safety Architecture — v28.0.2 "Ease"

Loofi Fedora Tweaks is built with a defensive security architecture designed to prevent unintended modifications, privilege escalation exploits, and system instability.

---

## 1. Principle of Least Privilege

- **Unprivileged Execution**: The application binary (`loofi-fedora-tweaks`) runs entirely as your normal desktop user.
- **Root Launch Prohibited**: Launching the GUI via `sudo` or as the `root` user is explicitly blocked at startup. Running GUI applications as root creates security risks and pollutes home directory ownership permissions.
- **On-Demand Escalation**: When a persistent system modification is required, privilege escalation is requested strictly for that individual transaction using `pkexec` and your desktop's Polkit agent.
- **No Custom Policy Packages**: Loofi uses existing system Polkit policies; it does not install persistent custom sudoers rules or insecure policy overrides.

---

## 2. Action Center: The Mutation Boundary

All persistent system changes are funneled through the **Changes** workspace (the Action Center). No other component or tab in the application can directly invoke mutating shell commands.

```text
[User Request]
       │
       ▼
1. Preflight Check   ───► Validates disk space, locks, prerequisites
       │
       ▼
2. Closed Plan       ───► Allowlisted action definition with typed schema
       │
       ▼
3. Polkit Escalation ───► Desktop pkexec prompt for administrative auth
       │
       ▼
4. Bounded Exec      ───► Argument array execution (shell=False, timeout-bounded)
       │
       ▼
5. Independent Verify───► Separate probe confirms actual host configuration
       │
       ▼
6. Journal Record    ───► Immutable entry saved to Trusted Change Journal
```

---

## 3. Subprocess Safety Standards

- **No Shell Execution**: Subprocesses are executed using direct argument arrays (e.g. `['dnf5', 'clean', 'all']`). The Python `shell=True` argument is forbidden across all services.
- **No Command Interpolation**: Commands cannot accept untrusted strings, unvalidated user input, or arbitrary shell pipelines.
- **Strict Timeout Bounds**: Every execution is constrained by a timeout (default 300 seconds) to prevent hanging processes or deadlocks.
- **Exclusive Mutation Lease**: Only one mutating action plan can be active at any given moment. Concurrent mutations are rejected.

---

## 4. Independent Verification

In traditional scripts, an exit code of `0` is often blindly assumed to mean success. Loofi enforces **Verification Separation**:
- After execution, an independent inspection probe queries the host subsystem directly.
- For example, after updating a service or package, Loofi queries `systemctl` or package metadata to prove the change is actually present in the live system.
- If verification fails or is incomplete, the plan is marked as unverified rather than successful.

---

## 5. State Integrity & Privacy

- **Atomic Persistence**: Core state stores using the hardened atomic writer use a temporary file, `fsync`, atomic replacement, directory `fsync`, and readback verification. Legacy preference settings use a temporary file and atomic replacement, but do not claim `fsync` durability.
- **Zero Secret Retention**: Loofi never solicits, stores, or caches administrative passwords, authentication tokens, or private encryption keys.
- **Sanitized Support Export**: When exporting a diagnostic support bundle for bug reporting, sensitive paths, environment secrets, and credentials are automatically redacted.

---

## 6. Eliminated Attack Surfaces

Unlike legacy system tweak utilities, Loofi deliberately avoids:
- **No Background Daemon**: Eliminates background privilege escalation vulnerabilities and memory leaks.
- **No Web API / Listening Ports**: Eliminates remote code execution and local port exposure risks.
- **No Unvetted Script Repositories**: All action definitions and providers are audited, typed, and compiled into the core application.
