# CLI Reference — v27.0.1 "Core"

The Core CLI is a bounded inspection and review interface. It never accepts
arbitrary shell text or command vectors. Put global flags before the command.

```bash
loofi-fedora-tweaks --cli --help
loofi-fedora-tweaks --cli --json info
```

Recommended alias:

```bash
alias loofi='loofi-fedora-tweaks --cli'
```

## Global flags

| Flag | Purpose |
| --- | --- |
| `--json` | Emit a stable machine-readable envelope |
| `--timeout N` | Bound inspection or execution time |
| `--dry-run` | Show a review without executing a mutation |
| `--version` | Print the installed version |

## Top-level commands

| Command | Purpose |
| --- | --- |
| `info` | Show version, Fedora, session, and package/deployment facts |
| `check` | Run and persist the explicit read-only System Check |
| `updates` | Inspect system, Flatpak, firmware, conflicts, and history |
| `troubleshoot` | List, run, inspect, compare, and export bounded profiles |
| `changes` | List, show, apply, and verify Action Center plans/runs |
| `activity` | Inspect the Trusted Change Journal and recovery guidance |
| `doctor` | Check dependencies, Fedora version, and authorization readiness |
| `support-bundle` | Export a redacted support bundle ZIP |

## Common read-only workflows

```bash
loofi info
loofi --json check
loofi updates check
loofi updates conflicts
loofi updates history
loofi troubleshoot profiles
loofi troubleshoot run <PROFILE_ID>
loofi changes list
loofi changes show <PLAN_OR_RUN_ID>
loofi activity list --limit 25
loofi doctor
loofi support-bundle
```

## Review and verification

Persistent changes use the same lifecycle as the GUI:

`request → plan → fresh preflight → explicit confirmation → bounded execute →
independent verify`.

Inspect first, then apply a saved plan or a registered Action Center action
with closed typed parameters. `--dry-run` only emits the plan; it does not
change the host.

```bash
loofi changes list
loofi changes show <PLAN_ID>
loofi changes apply <PLAN_ID> --yes
loofi changes verify <RUN_ID>
```

An unavailable, stale, unsupported, or unverifiable result remains explicit.
Unknown Fedora deployment or session detection fails closed. No CLI command
starts a daemon, schedules work, reboots, retries, or rolls back automatically.

## Compatibility note

Specialist commands, the local Web API, D-Bus daemon commands, duplicate app
catalogue operations, and generic cleanup/tuning entrypoints are not part of
the v27.0.1 public CLI. Existing scripts should migrate to the commands above
and branch on typed result states rather than parsing shell output.
