# Loofi Fedora Tweaks — Advanced Admin Guide

> Version 25.0.4 "Proof" public release

Operational runbook for power users and Fedora administrators.

---

Proof adds bounded direct execution and outcome evidence over the existing
Action Center. Physical and manual qualification remain separately reported
gates; this guide does not treat rootless evidence as host qualification.

## 1) Operating Model

Loofi entry modes:

- GUI: `loofi-fedora-tweaks`
- CLI: `loofi-fedora-tweaks --cli ...`
- daemon: `loofi-fedora-tweaks --daemon`
- optional Web API: `loofi-fedora-tweaks --web`

The primary shell exposes Home, Software & Updates, System, Network & Security,
Desktop, and Settings. Specialist Tools remains grouped and searchable without
a global mode switch. `Ctrl+K` searches all policy-visible routes and settings;
`Ctrl+Shift+K` uses the same search model filtered to actions.

The base package uses logical core/specialist isolation. It does not ship a
physical `-extras` RPM. Core startup registers application-owned, data-only
provider specifications without importing specialist UI modules, and page
instances are created on demand. External Python plugin discovery and execution
are retired. CLI, API, daemon, IPC, and stable route contracts remain
independent of the current GUI surface.

Platform behavior:

- Traditional Fedora uses DNF.
- Atomic Fedora uses rpm-ostree-aware paths and keeps unsupported mutations
  manual-only.

---

## 2) Privilege and Safety

Privileged workflows rely on `pkexec`, the desktop polkit agent, and the
installed `org.loofi.fedora-tweaks.policy` file. Never run Loofi with `sudo`.

Verification:

```bash
which pkexec
pkexec true
ls /usr/share/polkit-1/actions/org.loofi.fedora-tweaks.policy
```

Action Center is the only GUI that owns the verified maintenance
plan/run/verify lifecycle. Home and global search may navigate or preselect,
but cannot execute. The catalog contains 74 classified first-party definitions;
unsupported host operations are explicit `manual_only` plans.

Operational invariants:

- plans expire and receive a fresh apply-time preflight;
- execution requires explicit confirmation;
- medium/high-risk no-rollback paths require a separate acknowledgement;
- a cross-process lease allows one mutation at a time;
- verification is separate from command execution;
- interrupted runs are preserved without automatic resume, retry, or rollback.

Read-only review commands:

```bash
loofi action-center list --target 44
loofi action-center history --limit 20
loofi action-center recommendations --target 44
```

---

## 3) Weekly Maintenance Window

1. Create a recovery point from **System → Recovery Points**.
2. Review Home attention items and **Software & Updates → Upgrade Assistant**.
3. Inspect supported maintenance in **Software & Updates → Action Center**.
4. Run **Software & Updates → Updates**.
5. Run reclaim analysis from **Software & Updates → Cleanup**.
6. Validate **Network & Security → Security** and firewall state.
7. Review **System → Performance**, Processes, Storage, and Troubleshooting for
   regressions.

![Upgrade Assistant](images/user-guide/upgrade-assistant.png)

![Maintenance Updates](images/user-guide/maintenance-updates.png)

![Security and Privacy](images/user-guide/security-privacy.png)

---

## 4) Core Workflow Runbooks

### Update the system

Use **Software & Updates → Updates**. Preserve preview and confirmation steps.
On Atomic Fedora, follow rpm-ostree guidance rather than forcing a DNF path.

### Install an application

Use **Software & Updates → Applications**. Confirm package source and requested
change before installation.

### Diagnose a slow system

Run **System → Performance → Analyze Slow System** while the problem is active.
Use the bounded snapshot to select the next inspection route. Do not tune,
restart, or delete based on a single metric.

![System Monitor](images/user-guide/system-monitor.png)

For a broader guided session, open **System → Troubleshooting**, select
`system_slow`, inspect the exact source budget, and start collection
explicitly. Treat **Possibly related** changes as correlation, not causation.
Use a compatible explicit rerun after any independently verified action;
Action Center `verified` never implies troubleshooting `resolved`.

### Free disk space

Run **Software & Updates → Cleanup → Analyze Reclaimable Space**. Treat package
cache, journal retention, and trim separately. DNF cache cleanup is
manual-only on Atomic Fedora.

### Protect or recover

Use **System → Recovery Points** for snapshots, **Network & Security → Backups**
for guided backup/restore, and **Settings → Repair Loofi** for state inspection.
These surfaces reuse the established state, archive, and recovery contracts.

---

## 5) Advanced and Specialist Operations

Performance Tuning, Gaming, Development, Local Profiles, Loofi Link, AI Lab,
Agents, Automation, State Teleport, Virtualization, Profiles, and Extensions
belong to the grouped logical specialist component.

If a specialist component is unavailable, the route remains fail-closed with
an explanation. The six Standard destinations and five core workflows must
remain usable. Do not work around an unavailable result by importing a missing
UI module manually.

Local profiles are explicit, data-only JSON. The Legacy Extensions view can
inventory and export existing third-party directories, but it never imports or
deletes their code. There is no supported Marketplace installation or external
plugin execution path.

---

## 6) CLI Automation Patterns

Alias:

```bash
alias loofi='loofi-fedora-tweaks --cli'
```

Health snapshots:

```bash
loofi --json info > /tmp/loofi-info.json
loofi --json health > /tmp/loofi-health.json
```

Maintenance inspection:

```bash
loofi action-center list --target 44
loofi readiness --target 44 --advanced
loofi logs errors --since "24h ago"
loofi security-audit
```

Service and package triage:

```bash
loofi service list --filter failed
loofi service status sshd
loofi package recent --days 7
```

Use `--json` for automation and `--dry-run` where the command supports a
preview. Do not strip Action Center confirmation flags or reuse expired plan
IDs in scripts.

---

## 7) Daemon and Web API Notes

```bash
loofi-fedora-tweaks --daemon
loofi-fedora-tweaks --web
```

The daemon and API retain their package names and exact base-package EVR
dependency. The API accepts loopback bindings only. Apart from rate-limited
token issuance, its only write is `POST /api/action-center/plans`, which accepts
one known definition and closed parameter object and never applies the returned
plan. Manage the local API credential with `api-key
status`, `api-key rotate`, and `api-key revoke`. The daemon may create plans but
cannot confirm or execute host changes; GUI mode selection does not broaden
either surface.

Authenticated `GET /api/system-check/latest` returns only the latest bounded,
privacy-safe persisted System Check result. It performs no collection. There
are equivalent retrieval-only troubleshooting endpoints at
`GET /api/troubleshooting/latest` and
`GET /api/troubleshooting/sessions/SESSION_ID`. They read retained sessions
only. There is no API endpoint to start a check or troubleshooting session,
confirm or apply a plan, execute maintenance, or claim finding resolution.
Use `loofi --json troubleshoot latest` and
`loofi --json troubleshoot compare SESSION_ID FOLLOWUP_ID` for the versioned
CLI payload.

---

## 8) Incident Response Quick Playbooks

Application failure:

```bash
tail -n 200 ~/.local/share/loofi-fedora-tweaks/startup.log
loofi doctor
```

Privilege failure:

```bash
which pkexec
pkexec true
```

State and support evidence:

```bash
loofi --json state doctor
loofi support-bundle
journalctl --user --since "2 hours ago"
```

---

## 9) Data Paths and Upgrade Integrity

- `~/.config/loofi-fedora-tweaks/settings.json`
- `~/.config/loofi-fedora-tweaks/profile.json`
- `~/.config/loofi-fedora-tweaks/first_run_complete`
- `~/.local/share/loofi-fedora-tweaks/startup.log`

Proof preserves settings, navigation migration inputs, favorites, stable
routes, and observability data. Writable Action Center v1-v3 state migrates
atomically to schema v4; unknown future schemas remain read-only. Optional
troubleshooting schema-v1 state retains at most 20 terminal sessions and also
fails read-only on unknown future schemas. RPM scriptlets do not own or migrate
per-user XDG state.

---

## 10) Cross References

- Beginner: `docs/BEGINNER_QUICK_GUIDE.md`
- Full user guide: `docs/USER_GUIDE.md`
- Verified maintenance: `docs/VERIFIED_MAINTENANCE.md`
- Troubleshooting: `docs/TROUBLESHOOTING.md`
