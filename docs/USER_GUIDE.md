# Loofi Fedora Tweaks — User Guide

> Version 27.0.1 "Core"

This guide covers the supported GUI and CLI surfaces. For a short first run,
see [Getting Started](BEGINNER_QUICK_GUIDE.md). For operator detail, see
[Advanced administration](ADVANCED_ADMIN_GUIDE.md).

## 1) Product scope

Loofi is a focused Fedora maintenance core. It combines read-only inspection,
safe handoff to native desktop tools, and reviewed system changes in one
application. The product has five destinations:

| Destination | Purpose |
| --- | --- |
| **Home** | Current status, one recommended next action, and common tasks |
| **Updates & Apps** | System, Flatpak, and firmware checks; native software-center handoff |
| **System Health** | System Check, troubleshooting, storage, hardware, and support export |
| **Protection & Recovery** | Firewall exposure, backups, recovery points, and rollback guidance |
| **Changes** | Review, authorization, execution, and verification of persistent changes |

Application settings are opened from the header gear. There is no separate
specialist product, background service, remote API, or sandbox distribution.

Unknown desktop, session, or deployment detection is shown as unavailable. It
does not silently become a traditional Fedora or “no restart needed” result.

## 2) Install and launch

Install the published Fedora package from COPR:

```bash
pkexec dnf copr enable loofitheboss/loofi-fedora-tweaks
pkexec dnf install loofi-fedora-tweaks
```

Launch from the application menu or run:

```bash
loofi-fedora-tweaks
```

For a source checkout:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
PYTHONPATH=loofi-fedora-tweaks python3 loofi-fedora-tweaks/main.py
```

The optional `install.sh` helper is guarded because a published RPM is easier
to audit than a downloaded shell script. It never runs the application as
root:

```bash
bash install.sh --i-know-what-i-am-doing
```

## 3) Home

Home reads saved state and displays one prioritized next action. On a new
installation it says **No system check has been run yet** and offers one
**Run system check** action. Constructing Home, opening a page, or following a
saved run does not collect new data or mutate the host.

After a check, Home distinguishes healthy, attention-needed, unavailable, and
failed sources. A pending restart or pending verification remains visible
until its own follow-up confirms the result.

## 4) Updates & Apps

Updates follows one source at a time through this sequence:

1. **Check** — collect a bounded source-specific result.
2. **Select source** — choose system packages, Flatpak, or firmware.
3. **Review changes** — inspect the exact summary, risk, and restart expectation.
4. **Run** — confirm the reviewed plan in Changes.
5. **Verify** — inspect the source again and record the outcome.

An unavailable source is not the same as an up-to-date source. Missing tools,
missing remotes, unsupported deployment backends, and failed probes remain
explicit in the result.

Application installation is not a second software store. When the desktop
advertises a native software center, Loofi hands the selected AppStream item to
that application; otherwise it explains why no safe handoff is available.

## 5) System Health

System Health contains read-only System Check, symptom-driven troubleshooting,
storage inspection and reclaim analysis, hardware status, and support export.
Choose a symptom, review the bounded checks, and start collection explicitly.
Results identify missing or partial sources and offer at most one safe next
step. No repair starts as a side effect of inspection.

Support bundles are redacted and bounded. They contain diagnostic facts and
selected history, not secrets, arbitrary command output, or executable repair
instructions.

## 6) Protection & Recovery

Protection & Recovery provides firewall and exposure inspection, backup and
recovery-point workflows, supported rollback guidance, and activity history.
Each operation states its capability, risk, required authorization,
verification method, and recovery limits before it can be reviewed.

## 7) Changes

Changes is the only workspace that can create and run a persistent system
change. It is divided into **Needs attention** and **Recent**, with a
state-driven primary action. Every item explains five things:

1. what will change;
2. the risk and affected scope;
3. why authorization is needed;
4. how the result will be verified; and
5. what recovery or manual follow-up exists.

The lifecycle is:

```text
preflight → review → explicit authorization → bounded run → independent verify
```

Plans expire, are checked again immediately before execution, and are protected
by a single mutation lease. A successful process exit is not treated as a
verified result. No automatic restart, retry, rollback, or resume occurs.

## 8) CLI

The CLI deliberately mirrors the five core journeys:

```bash
alias loofi='loofi-fedora-tweaks --cli'

loofi info
loofi check
loofi updates check
loofi troubleshoot profiles
loofi troubleshoot run system_slow
loofi changes list
loofi changes show PLAN_ID
loofi changes verify RUN_ID
loofi activity list
loofi doctor
loofi support-bundle
```

Use `--json` before the command for machine-readable output. The CLI accepts
only registered commands and typed parameters. It has no arbitrary shell,
remote execution, or hidden mutation mode.

## 9) Keyboard and accessibility

- `Ctrl+K` opens global search.
- `Ctrl+Shift+K` filters search to actions.
- `F1` opens shortcut help.
- `Esc` closes transient panels and dialogs.

Search results are pages first. An action result opens the corresponding review
surface; selecting it never executes a command. The UI remains usable with
keyboard navigation, high contrast, dark and light themes, and enlarged text;
physical assistive-technology qualification is tracked separately until run.

## 10) Troubleshooting the application

Run `loofi doctor` first. It reports missing desktop integration, unavailable
system tools, unsupported deployment backends, and authorization prerequisites
without changing the host. Then create a support bundle and include the
reported version, Fedora variant, exact page, and reproduction steps in an
issue.

See [Troubleshooting](TROUBLESHOOTING.md), [State integrity](STATE_INTEGRITY.md),
and [Verified maintenance](VERIFIED_MAINTENANCE.md) for deeper guidance.
