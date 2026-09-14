# Loofi Fedora Tweaks — Getting Started

> Version 28.0.2 "Ease" release candidate

<!-- Canonical source mirrored byte-for-byte to wiki/Getting-Started.md. -->

Use this guide for a safe first run in under 10 minutes.

## 1) Install and launch

```bash
pkexec dnf copr enable loofitheboss/loofi-fedora-tweaks
pkexec dnf install loofi-fedora-tweaks
loofi-fedora-tweaks
```

The first launch opens Home. Before the first check it shows an honest
not-yet-checked state and offers one **Run system check** action. Opening the
application or browsing a page does not probe or modify the host.

## 2) Learn the five destinations

1. **Home** — system status, one recommended next action, and common tasks.
2. **Updates & Apps** — system, Flatpak, and firmware checks plus native
   software-center handoff.
3. **System Health** — read-only checks, troubleshooting, storage, hardware,
   and support export.
4. **Protection & Recovery** — firewall exposure, backups, recovery points,
   and supported rollback guidance.
5. **Changes** — the single review and verification workspace for persistent
   changes.

Settings are opened with the header gear. There is no separate specialist
product, background daemon, web API, or sandbox distribution.

## 3) Three useful workflows

### Check for updates

Open **Updates & Apps**, choose **Check for updates**, select a source, review
the resulting plan, and run it from **Changes**. System, Flatpak, and firmware
results stay separate; unavailable is not reported as up to date.

### Diagnose a problem

Open **System Health → Troubleshooting**, choose one symptom, and start the
read-only check explicitly. Review the result and any safe next step. No repair
starts automatically.

### Review a change

Open **Changes** to inspect **Needs attention** and **Recent**. Each change
explains what will happen, risk, authorization, verification, and recovery.
Only an explicit confirmation runs a supported mutation, and verification is a
separate step.

## 4) Optional CLI

```bash
alias loofi='loofi-fedora-tweaks --cli'

loofi info
loofi check
loofi updates check
loofi troubleshoot profiles
loofi changes list
loofi activity list
loofi doctor
loofi support-bundle
```

Add `--json` before a command for machine-readable output. The CLI has the
same closed action catalog and safety boundary as the GUI.

## 5) Next docs

- [Full user guide](../docs/USER_GUIDE.md)
- [Verified maintenance](../docs/VERIFIED_MAINTENANCE.md)
- [State integrity](../docs/STATE_INTEGRITY.md)
- [Troubleshooting](../docs/TROUBLESHOOTING.md)
- [Documentation index](../README.md)
