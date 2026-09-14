# CLI Reference — v28.0.2 "Ease"

Loofi Fedora Tweaks provides a scriptable, read-first command-line interface. It enforces the exact same security boundaries and closed Action Center definitions as the graphical desktop interface: inspection is strictly read-only, and persistent host changes require review, explicit confirmation, and post-execution verification.

The CLI never evaluates arbitrary shell strings, never spawns background daemons, and rejects untyped command vectors.

---

## Global Syntax & Flags

```bash
loofi-fedora-tweaks --cli [GLOBAL_FLAGS] <COMMAND> [SUBCOMMAND] [OPTIONS]
```

Recommended shell alias:

```bash
alias loofi='loofi-fedora-tweaks --cli'
```

### Global Options

| Option | Type | Description |
| --- | --- | --- |
| `--json` | flag | Output results wrapped in a stable machine-readable JSON envelope |
| `--timeout <seconds>` | integer | Maximum execution timeout in seconds (default: 300) |
| `--dry-run` | flag | Generate and display the change plan without modifying the host |
| `-v`, `--version` | flag | Print application version and codename |

---

## The 8 Canonical Commands

```text
loofi
├── info             # Platform, desktop, kernel, and deployment profile
├── check            # Comprehensive read-only Fedora system check
├── updates          # Multi-source updates inspection (check, conflicts, history)
├── troubleshoot     # Symptom-driven troubleshooting (profiles, run, compare, export)
├── changes          # Action Center workspace (list, show, apply, verify)
├── activity         # Trusted Change Journal inspection (list)
├── doctor           # Self-diagnostics, Polkit agent check, dependency audit
└── support-bundle   # Export sanitized diagnostic archive (.zip)
```

---

## 1. `loofi info`

Outputs system identity, hardware architecture, desktop environment, display server, and Fedora deployment backend (`dnf5`, `rpm_ostree`, `bootc`, or `unknown`).

```bash
loofi info
loofi --json info
```

---

## 2. `loofi check`

Executes a full read-only System Check covering package manager consistency, failed systemd units, SELinux enforcement, and mount options. Saves results to the local state database.

```bash
loofi check
loofi --json check
```

---

## 3. `loofi updates`

Inspects software updates across system packages, Flatpaks, and firmware without conflating sources or hiding failures.

```bash
# Check update availability across all configured sources
loofi updates check

# Inspect known package or dependency conflicts
loofi updates conflicts

# View recent transaction history
loofi updates history
```

---

## 4. `loofi troubleshoot`

Provides symptom-driven diagnosis using allowlisted read-only checks.

```bash
# List available troubleshooting profiles
loofi troubleshoot profiles

# Run diagnosis for a specific symptom profile
loofi troubleshoot run system_slow
```

---

## 5. `loofi changes`

The exclusive CLI interface for reviewing, applying, and independently verifying persistent system changes.

```bash
# List active plans and recent completed runs
loofi changes list

# Inspect full plan details, risk tier, and parameters
loofi changes show PLAN_ID

# Confirm and execute a reviewed change plan
loofi changes apply PLAN_ID --yes

# Independently verify that the change completed as expected
loofi changes verify RUN_ID
```

---

## 6. `loofi activity`

Queries the Trusted Change Journal for past maintenance operations.

```bash
# List recent change entries with outcome status
loofi activity list
```

---

## 7. `loofi doctor`

Performs an environment self-audit: validates Python dependencies, checks Polkit agent availability for `pkexec`, verifies package manager tools, and identifies desktop integration status.

```bash
loofi doctor
loofi --json doctor
```

---

## 8. `loofi support-bundle`

Generates a sanitized ZIP archive containing non-sensitive system logs, environment facts, and recent change history for bug reporting. Sensitive user data, private keys, and passwords are automatically stripped.

```bash
loofi support-bundle
```

---

## Scripting with `--json` and `jq`

Using the `--json` flag formats all output into a predictable envelope. The envelope contains `status`, `data`, and `errors`.

```bash
# Extract Fedora deployment backend
loofi --json info | jq -r '.data.deployment_backend'

# Count pending updates
loofi --json updates check | jq '.data.total_updates'

# Check if SELinux is enforcing
loofi --json check | jq '.data.selinux.status'
```

---

## Safety & Non-interactive Execution

- **No Shell Expansion**: Arguments are passed directly as typed vectors.
- **Fail Closed**: Unknown Fedora variants, unrecognized desktop sessions, or missing Polkit agents halt execution rather than falling back to guessing.
- **Explicit Confirmation**: `loofi changes apply` requires `--yes` in automated scripts; otherwise execution aborts.

