# Loofi Fedora Tweaks — User Guide

> Version 29.0.1 "Utility" release

This guide covers the supported GUI and CLI. For a short first run, see
[Getting Started](BEGINNER_QUICK_GUIDE.md). For operator detail, see
[Advanced administration](ADVANCED_ADMIN_GUIDE.md).

## Product scope

Loofi is a curated Fedora utility with five primary destinations:

| Destination | Purpose |
| --- | --- |
| **Home** | Fedora profile, current status, recommendation, and job shortcuts |
| **Install** | Curated application search, category filters, source labels, and multi-select review |
| **Tune** | Editable Minimal, Recommended, and Power User selections |
| **Fix** | Symptom-first diagnostics and one supported next step |
| **Update** | Independent System, Flatpak, and Firmware state cards |

Activity & Recovery and Settings are secondary header surfaces. The product
has no background daemon, web API, arbitrary shell execution, or unattended
automation. Unknown desktop or deployment detection remains unavailable rather
than falling back to a Traditional Fedora assumption.

## Install and launch

```bash
pkexec dnf copr enable loofitheboss/loofi-fedora-tweaks
pkexec dnf install loofi-fedora-tweaks
loofi-fedora-tweaks
```

For a source checkout:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
PYTHONPATH=loofi-fedora-tweaks python3 loofi-fedora-tweaks/main.py
```

## Home

Home shows the immutable Fedora profile, a compact status row, one recommended
next step, shortcuts to Install, Tune, Fix, and Update, and current activity.
Loading Home never starts a host probe or mutation.

## Install

Install is a curated catalog rather than an unrestricted package browser.
Search by application name or goal, filter by category, and select several
items. Every row shows its source and availability.

Flatpak is preferred for ordinary GUI applications. Fedora RPM is used for
trusted system-integrated and command-line tools on Traditional Fedora. Atomic
systems show Flatpak first and mark layered RPM operations as advanced and
reboot-aware. Unsupported or unknown platforms fail closed.

Choose **Review selected applications** to inspect the bundle. Items execute
independently and keep separate terminal outcomes. The bundle never retries,
rolls back, or reboots automatically.

## Tune

Tune provides three editable starting points:

- **Minimal** — a small low-risk baseline.
- **Recommended** — broadly useful verified Fedora maintenance.
- **Power User** — additional implemented operations for experienced users.

Unavailable choices remain visible with an explanation. High-risk, boot,
display, and manual-only operations are excluded from automatic profiles.
Desktop-specific KDE or GNOME choices appear only when the capability is
known. Ordered operations stop after the first unexpected failure.

## Fix

Fix begins with a symptom such as a slow system, network trouble, storage
pressure, or boot/deployment concern. The diagnostic phase is read-only and
presents findings before it offers one safe next step. Depending on the
evidence, the next step is a supported verified operation, instructions, or a
native system-settings handoff. There is no **Fix all** action.

## Update

System, Flatpak, and Firmware are independent cards. Each card shows freshness,
availability, count, details, and exactly one primary action:

- **Check** collects a fresh source-specific result.
- **Update** prepares, applies, and verifies the selected source.
- **Continue** resumes post-reboot verification without rerunning the update.
- **Verify** checks the saved outcome again.

Missing tools, remotes, authorization, or supported backends remain explicit.
A source that could not be checked is never presented as up to date.

## Activity & Recovery

Activity groups **Needs you**, **In progress**, and **History**. It carries
verification failures, reboot follow-up, and recovery guidance only where the
saved operation requires them. Older `changes` and
`maintenance:action-center` links resolve to the corresponding Activity state.

## CLI

```bash
alias loofi='loofi-fedora-tweaks --cli'

loofi info
loofi check
loofi updates check
loofi troubleshoot profiles
loofi troubleshoot run system_slow
loofi activity list
loofi activity show EVENT_ID
loofi doctor
loofi support-bundle
```

Use `--json` before the command for machine-readable output. `changes` remains
a compatibility alias during v29 for Activity list/detail and explicit saved
plan completion. The CLI accepts registered commands and typed parameters only.

## Keyboard and accessibility

- `Ctrl+K` opens goal-based search.
- `F1` opens shortcut help.
- `Esc` closes transient panels and dialogs.

Search navigates to the task's owning page and returns focus to the selected
task. Theme, scaling, keyboard, and assistive-technology physical qualification
is recorded separately from offscreen automated checks.

## Support

Run `loofi doctor` first, then create a redacted support bundle. Include the
reported version, Fedora variant, exact page, and reproduction steps in an
issue. See [Troubleshooting](TROUBLESHOOTING.md),
[State integrity](STATE_INTEGRITY.md), and
[Verified operations](VERIFIED_MAINTENANCE.md) for deeper guidance.
