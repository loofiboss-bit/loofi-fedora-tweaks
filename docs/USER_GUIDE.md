# Loofi Fedora Tweaks — User Guide

> Version 32.1.0 "Wayfinder" (local candidate); physical desktop validation remains unverified.

This guide covers the supported GUI and CLI. For a short first run, see
[Getting Started](BEGINNER_QUICK_GUIDE.md). For operator detail, see
[Advanced administration](ADVANCED_ADMIN_GUIDE.md).

## Product scope

Loofi is a curated Fedora utility that opens on **Tweaks** and keeps four everyday
jobs in the sidebar:

| Destination | Purpose |
| --- | --- |
| **Tweaks** | Searchable GNOME and KDE settings with current values, reset to default, and undo |
| **Apps** | Curated application search, category filters, source labels, and multi-select review |
| **Updates** | Independent System, Flatpak, and Firmware state cards |
| **Health** | Symptom-first diagnostics, maintenance, and one supported next step |

System, Storage, Network, Security, and Logs are advanced pages. They appear only
after you enable **Show advanced tools** in Settings.

History & Undo and Settings are secondary header surfaces. The product
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

## Apps

Apps is a curated catalog rather than an unrestricted package browser.
Search by application name or goal, filter by category, and select several
items. Every row shows its source and availability.

Flatpak is preferred for ordinary GUI applications. Fedora RPM is used for
trusted system-integrated and command-line tools on Traditional Fedora. Atomic
systems show Flatpak first and mark layered RPM operations as advanced and
reboot-aware. Unsupported or unknown platforms fail closed.

Selections survive search and category changes. The summary and review include
hidden selected items; changing platform availability removes ineligible choices.

Choose **Review selected applications** to inspect the bundle. Items execute
independently and keep separate terminal outcomes. The bundle never retries,
rolls back, or reboots automatically.

## Tweaks

Combine All, Favorites, Changed, or Unavailable with a category and search.
Search includes application names such as Dolphin, Files, and Nautilus. Use
Clear filters when nothing matches. The star saves a per-setting favorite;
favorites never change desktop values. Choose one supported value. Each row shows its current
value, explanation, availability, and independently verified saved result.
Missing tools or unreadable values explain why the change is unavailable.
A pending choice appears beside the last verified value until readback finishes.
The row menu contains reset to default and technical details; the previous
verified value is offered separately. KWin changes also request a session
reconfigure and compare runtime values. A session warning preserves the saved
change and its restoration offer.

The catalog has 73 controls grouped as Appearance, Desktop, Files, Interaction,
Privacy, Input, Windows, Sound, Power, and System & Packaging. GNOME Files
offers click behavior and default folder view; KDE adds Dolphin's full-path
setting, editable location bar, session tabs, external folder tabs, and close-tab
confirmation. KWin offers maximized-titlebar, edge tiling, and focus prevention.
Files also offers an editable location bar and simple/detailed dates. Missing Files schemas or Dolphin
are reported as unavailable. See
[TWEAKS.md](TWEAKS.md) for the complete generated list with defaults.

Use **Reset to default** on a row whose value differs from its default, or turn on
**Changed from default** to list only those rows. Resetting runs through the same
checked change flow as any other change.

Custom numeric values remain visible and are preserved exactly when captured
for restoration. A power profile change asks for confirmation. Saved KDE
configuration may require reopening affected applications; saved verification
does not prove an immediate effect in open programs.

Choose **Restore previous value** on an eligible row to review its current and
previous values, then confirm. Loofi offers only the latest verified normal
change per setting. It reads the setting again before restoring and blocks if
it changed externally, a later change attempt exists, a scheme/profile was
removed, or history is missing. Older runs without restoration metadata and
pruned history cannot be restored. Successful restoration consumes the offer;
a new normal change creates a new offer. Restoration records a separate run
and verifies it independently. There is no automatic rollback, bulk restore,
or redo. A failed write or verification is shown as a failure rather than a
saved result.

## Health

Health begins with a symptom such as a slow system, network trouble, storage
pressure, or boot/deployment concern. The diagnostic phase is read-only and
presents findings before it offers one safe next step. Depending on the
evidence, the next step is a supported verified operation, instructions, or a
native system-settings handoff. Storage trim and package cache cleanup are
available here. There is no **Fix all** action.

Failed or unavailable probes remain explicit. A partial System Check preserves
useful findings alongside source errors; missing evidence never proves health.

## Updates

System, Flatpak, and Firmware are independent cards. Each card shows freshness,
availability, count, details, and exactly one primary action:

- **Check** collects a fresh source-specific result.
- **Update** prepares, applies, and verifies the selected source.
- **Continue** resumes post-reboot verification without rerunning the update.
- **Verify** checks the saved outcome again.

Missing tools, remotes, authorization, or supported backends remain explicit.
A source that could not be checked is never presented as up to date.

## History & Undo

Date filters accept ISO dates or finite Unix timestamps. Invalid dates or a
reversed interval stop loading and preserve the previously displayed result.

Activity groups **Needs you**, **In progress**, and **History**. It carries
verification failures, reboot follow-up, and recovery guidance only where the
saved operation requires them. Older `changes` and
`maintenance:action-center` links resolve to the corresponding Activity state.
Older Install, Tune, Fix, and Update route IDs continue to open their new pages.

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

### Custom scalar restoration bounds

Restoration preserves the captured scalar without display rounding. GNOME text
scale must be between 0.5 and 3; KDE animation duration must be finite and
nonnegative; KDE double-click interval must be an integer between 100 and
2000 ms. These custom values come only from verified saved evidence, not
arbitrary caller input. Invalid or unreadable values block modification.
