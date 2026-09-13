# Loofi Fedora Tweaks — Administration Guide

> Version 27.0.1 "Core"

This guide is for Fedora administrators who need repeatable diagnostics and a
clear boundary around system changes.

## Scope and trust boundary

Loofi ships one GUI and one intentionally small CLI. It has no background
daemon, web API, remote-control endpoint, plugin marketplace, or sandbox
distribution. Read-only inspection may run without administrator privileges.
Persistent changes are created and executed only through the Changes workspace
and its closed Action Center catalog.

The package uses the desktop's standard authorization agent through `pkexec`
when a reviewed system operation requires administrator approval. It does not
install project-specific Polkit policy files or grant standing privileges.

## Package installation

The supported Fedora package is published through COPR:

```bash
pkexec dnf copr enable loofitheboss/loofi-fedora-tweaks
pkexec dnf install loofi-fedora-tweaks
```

Install from a downloaded RPM only after verifying its release checksum and
source. The RPM contains the GUI, CLI, reviewed core services, assets, and
documentation; there are no API or daemon subpackages.

## Platform detection

At startup the core records an immutable platform profile containing the Fedora
release, architecture, desktop, session, and deployment backend. Supported
deployment backends are detected explicitly. If a value is unknown, dependent
actions remain unavailable and the report says what could not be determined.

This is a capability boundary, not a claim of identical desktop integration.
Native settings handoffs appear only when the relevant desktop capability is
known. Fedora Atomic variants may require a staged deployment and explicit
restart before verification; the application never restarts the host itself.

## Changes lifecycle

Inspect the candidate action in **Changes** and confirm that it names:

1. the exact change and affected resources;
2. risk and expected impact;
3. the required authorization;
4. the independent verification method; and
5. recovery guidance or the reason recovery is unavailable.

Execution regenerates the command from the registered definition, performs a
fresh preflight, acquires one cross-process mutation lease, and runs with a
bounded timeout. A process exit code is only an execution fact; the verifier
must confirm the resulting state. Interrupted and restart-required runs stay
visible and require an explicit follow-up.

## CLI operations

```bash
loofi-fedora-tweaks --cli info
loofi-fedora-tweaks --cli check --json
loofi-fedora-tweaks --cli updates check
loofi-fedora-tweaks --cli troubleshoot profiles
loofi-fedora-tweaks --cli changes list --json
loofi-fedora-tweaks --cli changes show PLAN_ID
loofi-fedora-tweaks --cli changes verify RUN_ID
loofi-fedora-tweaks --cli activity list --limit 25
loofi-fedora-tweaks --cli doctor
loofi-fedora-tweaks --cli support-bundle
```

The parser accepts only registered commands and closed parameter schemas. It
does not accept arbitrary command vectors, shell fragments, remote targets, or
unattended schedules.

## State and support

User configuration, action plans, runs, check results, activity history, and
backup metadata live under the user's XDG directories. Package removal does
not delete this state. Writes use atomic replacement, bounded backups, private
permissions, and readback. Unknown future schemas are read-only.

Use `doctor` to inspect prerequisites and `support-bundle` to export a bounded,
redacted diagnostic record. Review the bundle before sharing it. It must not
contain secrets, raw command output, or personal paths beyond the documented
redaction contract.

## Verification commands

From a source checkout:

```bash
just lint
just typecheck
just test
just check-packaging
just validate-release
just build-rpm
```

Rootless or offscreen results prove code contracts only. Fedora desktop,
authorization-agent, restart, Atomic deployment, and assistive-technology
qualification require the corresponding physical environment and remain
separate evidence until executed there.
