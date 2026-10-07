# Loofi Fedora Tweaks — User Guide

> Version 32.2.0 "Coherence"; physical desktop and assistive-technology validation remains unverified.

This guide covers the supported GUI and CLI. For a short first run, see
[Getting Started](BEGINNER_QUICK_GUIDE.md). For operator detail, see
[Advanced administration](ADVANCED_ADMIN_GUIDE.md).

## Product scope

Loofi is a curated Fedora control panel that opens on **Overview** and keeps
six primary destinations in the sidebar:

| Destination | Purpose |
| --- | --- |
| **Overview** | Read-only computer information, hardware measurements, and recent maintenance |
| **Tweaks** | Searchable GNOME and KDE settings with current values, verified changes, and supported recovery |
| **Apps** | Curated application search, category filters, source/scope labels, and multi-select review |
| **Updates** | Independent System, Flatpak, and Firmware status sections |
| **Health** | Symptom-first diagnostics, maintenance, and one supported next step |
| **Activity** | Recorded changes, verification results, recovery, and reboot follow-up |

Expand **Tools** for System, Storage, Network, Security, and Logs. It starts
collapsed and retains an existing advanced-tools preference. **Settings** sits
at the bottom of the sidebar. Search is in the header and opens with `Ctrl+K`.
The option to reopen the last page remains available in Settings.

The product has no background daemon, web API, arbitrary shell execution, or
unattended automation. Unknown desktop or deployment detection remains
unavailable rather than falling back to a Traditional Fedora assumption.

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

## Overview

Overview shows computer information and grouped CPU, memory, GPU, and storage
measurements, followed by network/disk activity, temperatures, and battery.
Separate GPUs and batteries keep their own readings. Root and home storage
are combined when they share a filesystem. A missing battery or unsupported
GPU measurement is explained; it is not displayed as zero.

Live CPU, memory, network, and disk measurements refresh every two seconds;
hardware sensors refresh every five seconds. Each reading includes its unit,
source, timestamp, and an explicit status. Hover a metric to inspect its source
and measurement time.

- **Collecting** means a measurement or initial rate baseline is pending.
- **Measured** means the displayed value was read successfully.
- **Unavailable** explains a missing device, unsupported field, or missing tool.
- **Read failed** identifies a measurement that could not be read.
- **Last known value** marks retained evidence that is no longer current.
- **High** or **Critical** uses a reported sensor threshold when one exists.

Graphs retain at most 60 measurements in memory and leave gaps for unavailable
readings. **Pause** holds the last recorded values; **Resume** starts a fresh
rate baseline. Overview and System Monitor share collection, which stops
scheduling measurements when neither view is visible or the window is hidden
or minimized. Sleeping GPUs are not queried automatically. No drivers or
monitoring tools are installed by opening the dashboard.

Recent maintenance reports recorded update and Health results with timestamps,
plus recent changes. A missing result remains unchecked; opening Overview does
not fabricate a successful check or run a repair. Existing startup-check
preferences still control startup checks.

## Apps

Apps is a curated catalog rather than an unrestricted package browser.
Search by application name or goal, filter by category, and select several
items. Every row shows its source, installation scope, and availability.
The selected-app summary and **Review selected applications** stay visible below
the scrolling catalog, including selections hidden by filters.

Flatpak is preferred for ordinary GUI applications. Fedora RPM is used for
trusted system-integrated and command-line tools on Traditional Fedora. Atomic
systems show Flatpak first and mark layered RPM operations as advanced and
reboot-aware. Unsupported or unknown platforms fail closed.

Apps shows Flathub status separately for system and user scopes before review.
Installation follows Flatpak's configured default scope. A missing source opens
the existing manual setup guidance; an unknown result explains why and can be
checked again. Loofi never enables a source automatically, and the install
preflight checks requirements again before execution. Selected apps remain
selected when you visit setup guidance and return.

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
An interrupted or failed change returns the control to the verified value and
shows its outcome on the row.
The current-state check has a shared 20-second limit. Progress reports how many
settings have been checked; cancelling or reaching the limit keeps completed
results and leaves unchecked values explicitly unknown.
The row menu contains **Use Loofi standard value** and technical details. This
curated reference may differ from the value the desktop chooses when a setting
is unset. The previous verified value is offered separately when history
permits restoration. KWin changes also request a session
reconfigure and compare runtime values. A session warning preserves the saved
change and its restoration offer.

The catalog has 73 controls grouped as Appearance, Desktop, Files, Interaction,
Privacy, Input, Windows, Sound, Power, and System & Packaging. GNOME Files
offers click behavior and default folder view; KDE adds Dolphin's full-path
setting, editable location bar, session tabs, external folder tabs, and close-tab
confirmation. KWin offers maximized-titlebar, edge tiling, and focus prevention.
Files also offers an editable location bar and simple/detailed dates. Missing Files schemas or Dolphin
are reported as unavailable. See
[TWEAKS.md](TWEAKS.md) for the complete generated list with Loofi standard values.

Use **Use Loofi standard value** on a row whose value differs from that
reference, or turn on **Changed** to list those rows. Resetting runs through the
same checked change flow as any other change. This operation is separate from
**Restore previous value**, which restores an eligible value recorded by Loofi.

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

## Activity

Date filters accept ISO dates or finite Unix timestamps. Invalid dates or a
reversed interval stop loading and preserve the previously displayed result.

Select a change to inspect its recorded before/after evidence, verification,
and supported recovery guidance. **Restore previous value** and **Use Loofi
standard value** remain separate actions; recovery always requires a fresh
review.

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

## Settings and appearance

Open **Settings** at the bottom of the sidebar. Appearance, Behavior, Advanced,
Repair Loofi, and About keep related settings together. Saved or failed changes
are reported next to the affected setting. Favorites, history, and existing
user preferences are preserved.

**Follow system theme** selects Loofi's light or dark palette from the desktop
color mode. Turning it off enables the explicit dark, light, or high-contrast
choice. The application keeps the system font and uses the same control
geometry in all themes.

## Keyboard and accessibility

- `Ctrl+K` opens the header search. Results navigate and focus a control; they do not execute changes.
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

## Everyday workflows

Overview shows up to three next steps, prioritizing pending or failed operations,
critical Health findings, and fresh available updates. Old or missing observations
lead to a check. These links never start a system change.

Updates loads saved observations and Action Center runs when opened. Continue and
Verify resume verification only. Interrupted or failed verification links to Activity;
a fresh check is deliberate. Corrupt history is a read error, never an empty success.

Tweaks offers **Save current settings…** and **Load profile…**. Select settings to
include or change, review current and desired values, and confirm the immutable
review. Identical, unsupported, and unavailable entries are skipped or disabled.
Changes stop on cancellation, changed baseline, or failed verification. Restore
supported changes from local verified Activity history. See [profile details](TWEAK_PROFILES.md).

Apps includes **Installed** with Flatpak source, installation, ref, version, and
reported size. The same app in two installations appears twice. Inspect permissions
or review removal of exactly one installation. Running apps must be closed first;
removal preserves their data. RPM removal opens the desktop software manager.

Health has separate **Sound is not working** and **Bluetooth is not working**
profiles. Each has a 15-second budget and cancellation. Missing tools, partial
responses, and timeouts remain unknown or unavailable. Open the native sound or
Bluetooth settings, make changes there, then recheck. Only the user can confirm
that sound plays or a device connects.

CLI equivalents use the same services and action authority:

```bash
loofi tweaks profile export --help
loofi tweaks profile preview --help
loofi tweaks profile apply --help
loofi apps installed --help
loofi apps remove --help
```

Profile apply requires confirmation. Flatpak removal requires an explicit
installation and confirmation; consult command help for exact arguments.
