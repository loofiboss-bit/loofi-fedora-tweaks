# Loofi Fedora Tweaks — User Guide

> Current local candidate: 32.8.0 "Guide". Physical desktop and assistive-technology qualification is recorded separately.

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

## Everyday guides

Overview offers four optional guides: **Make Fedora yours**, **Choose and
manage apps**, **Maintain your system**, and **Solve a problem**. Each step opens
the existing page or focuses its relevant control. Opening a step does not
install or remove packages, change settings, or run a diagnostic. The owning
page still asks you to start any check and review every proposed change.

Mark a step **Reviewed** after inspecting it or **Skip** when it does not apply.
Where a step supports it, link one exact successful operation or completed
diagnostic result. A linked result records that saved result only; it does not
mean the computer is currently healthy. Missing history is shown as unavailable.
Guide progress is stored locally under the application data directory. It can
be resumed after restarting Loofi, while checks and change reviews must still be
made again when needed. The separate guide format does not alter tweak profiles
or operation history.

The header guide menu stays available while visiting other pages. It offers the
next unfinished step and a return to the selected guide. Global search also
finds guide titles and terms such as “battery”, “choose apps”, and “free space”.
Search opens guidance; it does not start a check or change.

The read-only CLI can list and inspect guides, including JSON for scripts:

```bash
loofi-fedora-tweaks --cli guides list
loofi-fedora-tweaks --cli --json guides list
loofi-fedora-tweaks --cli guides show make-fedora-yours
loofi-fedora-tweaks --cli --json guides show solve-a-problem
```

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

## Personal everyday workflows

In Apps, choose **Installed** to search Flatpaks and visible RPM-owned desktop
applications, including RPM apps outside the curated catalog. Several launchers
and installed architectures of one RPM package share a row; reported size sums
those installed package instances. RPM identifies a package format, not its
origin or trust. The curated catalog remains separate. RPM management opens
the desktop software manager; partial reads say which source is incomplete.

In **My profile library**, select **Edit a copy…** to change the name, included
settings, and supported target values. **Save new version** preserves the original
and changes no computer settings. Unknown/unavailable originals are retained
until you clear their inclusion box. Review the saved copy separately to apply it.

In Apps, choose **Package sources** to search all locally configured DNF5 sources
by ID, name, and activation status. **View package sources** in Updates opens the
same view. Observation time describes when configuration was read; it does not
prove network availability. Refresh reads configuration without downloading metadata.

```bash
loofi-fedora-tweaks --cli updates sources
loofi-fedora-tweaks --cli --json updates sources
```

Tweaks adds **New window placement**, **Snap distance to screen edges**, and
**Snap distance to other windows** on supported KDE installations. Saved-value
verification is separate from activation in the current KWin session. Restore
supported previous values from Activity. Apps also opens KDE default applications;
Tweaks opens autostart and icon settings after checking the requested native module.

## Companion workflows

### Keep your own desktop profiles

In Tweaks, open **My profile library**. Built-in profiles include Focus,
Privacy basics, Touchpad comfort, Reduced motion, and File navigation.
Review one profile to see current and requested values before selecting changes.
Save selected supported settings as a personal profile, import a shared JSON
profile, or export a local profile for another computer using the same desktop.
Built-in profiles cannot be removed. Removing a personal profile removes only
the local saved file; it does not revert desktop settings.

```bash
loofi-fedora-tweaks --cli tweaks profile library list
loofi-fedora-tweaks --cli tweaks profile library add my-settings.json
loofi-fedora-tweaks --cli tweaks profile library remove PROFILE_ID
loofi-fedora-tweaks --cli tweaks preset preview focus
```

### Understand an application's access

Select an installed Flatpak in Apps and inspect its access. Metadata and
global/application overrides remain separate. Overrides apply to an app ID
and can affect more than one installed branch. Portal grants and one-time
launch arguments are outside this report; it does not guarantee actual access.
Use the offered installed permission tool to make a change, then explicitly
refresh the observation. Loofi does not change app permissions itself.

```bash
loofi-fedora-tweaks --cli apps access app/org.mozilla.firefox/x86_64/stable --installation user
```

### Compare a symptom and prepare a support question

In Health, select a symptom and deliberately run its check. Select an earlier
saved session as a baseline to compare findings after a follow-up check.
An incomplete or incompatible source remains **Not comparable**. A resolved
finding means compatible evidence no longer contains it, not that every part
of the problem has been physically tested.

For screen-sharing problems, the check observes the session, PipeWire,
WirePlumber, and portal support. It does not capture your screen or restart
services. Test sharing in your application yourself after following guidance.

Choose **Prepare a support question**, select the saved session, and describe
the problem and reproduction steps. Review and edit the masked preview before
exporting Markdown or ZIP. Exports stay local and do not run another check.
Review the file yourself before sharing: masking is not full anonymization.

### Prepare for a Fedora version upgrade

In Updates, choose **Prepare for a Fedora upgrade**, select a policy-defined
target, and run the local inspection. Read the package database, source,
storage, and reboot observations independently. Confirm the backup checklist
only after checking your own backup and recovery arrangements.

```bash
loofi-fedora-tweaks --cli updates prepare-upgrade --target 44
```

Use a newer target offered by the installed policy; the example may be the
current version on your computer. Preview targets are explicitly labeled.
Local observations do not certify that the target transaction will work or
that free space is sufficient. Missing DNF restart-hint support is **Unknown**.
Follow the official upgrade documentation to perform the actual version change.
Atomic deployments receive limited observations and manual guidance.

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

The catalog has 82 controls grouped as Appearance, Desktop, Files, Interaction,
Privacy, Input, Windows, Sound, Power, and System & Packaging. GNOME Files
offers click behavior and default folder view; KDE adds Dolphin's full-path
setting, editable location bar, session tabs, external folder tabs, and close-tab
confirmation. KWin offers maximized-titlebar, edge tiling, and focus prevention.
Files also offers an editable location bar and simple/detailed dates. Missing Files schemas or Dolphin
are reported as unavailable. See
[TWEAKS.md](TWEAKS.md) for the complete generated list with Loofi standard values.

Choose **Choose preset…** to review **Reduced motion** or **File navigation**
for the detected desktop. Each supported setting shows its current and proposed
value. Unavailable settings explain why; identical values are skipped. Uncheck
any change you do not want, then confirm to apply the remaining changes one at a
time. A failed verification stops the rest; completed changes remain in Activity.

Use **Check current value** in a row's action menu to reread only that setting
and its restoration offer. The check has an eight-second shared limit. If it
fails or is cancelled, the row is marked unavailable until its next successful
check; the other rows and filters remain as they were.

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
reported size. The same app in two installations appears twice. **Show permissions**
opens a read-only, installation-bound view of permissions declared by that app's
metadata, grouped by network, files, audio, devices, display, and D-Bus. Environment
values are hidden; unknown keys remain under **Technical details**. Portals and
user overrides can change actual access.
**Review removal** always targets exactly one installation. Running apps must be
closed first; removal preserves their data. RPM removal opens the desktop software manager.

### Care app details and runtime maintenance

In **Installed**, combine search with source and installation filters. Choose
**Largest first** to sort the reported logical sizes; missing sizes remain unknown
and sort last. Filtering and sorting do not start a new inventory probe.

**App details** reads the exact Flatpak ref and installation. It shows the source
remote name, runtime, reported size, and locally recorded app/runtime end-of-life
warnings or replacement refs. No recorded warning is not a continued-support
guarantee. Permission metadata remains available through **Show permissions**.
Source URLs and private environment values are not displayed.

In **Unused Flatpak runtimes**, choose user, system, or a named installation.
**Refresh installations** explicitly discovers named installations; you may also
enter their name. **Inspect unused runtimes** reads local libflatpak evidence,
then lets you select exact refs for **Review runtime cleanup**. The reviewed
snapshot binds candidates, commits, pinning and visible dependency evidence.
Changes to it require a new review. The operation preserves app data and checks
the selected and remaining refs independently. A partial or interrupted removal
keeps its observed refs in Activity; recovery is manual reinstallation.

System and named installations are shared. The invoking user's dependency
evidence can be inspected, but other users' private app inventories are not.
Reported ref sizes include shared objects and are not a promise of freed space.
Missing optional PyGObject/libflatpak support is unavailable; Loofi never
installs these dependencies automatically.

CLI examples (replace refs and installation names with inspected values):

```bash
loofi-fedora-tweaks --cli apps details app/org.mozilla.firefox/x86_64/stable --installation user
loofi-fedora-tweaks --cli apps unused --installation user
loofi-fedora-tweaks --cli apps cleanup --installation user --ref runtime/org.example.Unused/x86_64/stable
```

The cleanup command previews without `--yes`. Adding `--yes` explicitly accepts
the exact reviewed runtime removal and manual reinstallation without rollback.
Repeat `--ref` to select more runtimes. Global `--dry-run` never starts removal.

### Diagnose one update source

Failed check, update and verification cards offer **Diagnose**. The link opens
Health with the source and exact recorded run selected, without running a check.
Choose **Run diagnostics** explicitly. System uses existing package/deployment
checks; Flatpak inspects local inventories, remotes and runtimes; Firmware
inspects fwupd service and device availability. Failed or malformed evidence
remains partial or unavailable. These checks do not update, repair or retry.

```bash
loofi-fedora-tweaks --cli --json updates check
loofi-fedora-tweaks --cli --json updates diagnose --source flatpak
loofi-fedora-tweaks --cli updates diagnose --source firmware --run-id RECORDED_RUN_ID
```

CLI and GUI update discovery share source observations. CLI returns a nonzero
status when a source fails or cannot be checked, preserving useful source results.
An exact run must belong to the selected source; missing or mismatched history
does not select a different operation.

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
loofi tweaks preset list
loofi tweaks preset preview reduced-motion
loofi tweaks preset apply file-navigation --yes
loofi apps installed --help
loofi apps permissions app/org.mozilla.firefox/x86_64/stable --installation user
loofi apps remove --help
```

Profile and preset apply require `--yes` to change settings. Flatpak permission
inspection and removal require an explicit installation; removal also requires
confirmation. Permission JSON hides environment values.

### KDE appearance and pointers

Under **Tweaks → Appearance**, choose an installed pointer theme, a requested
pointer size (24, 32, 48 or 64), or an installed Plasma style for panels and
widgets. Pointer controls require KDE Wayland; KDE X11 instead offers an
explicit **Open Cursor Settings** button after the native module is checked.
Plasma style is separate from the existing color scheme. Themes are not
downloaded or installed by these controls.

Changing a pointer theme preserves its saved size; changing the size preserves
the theme. Loofi reads both values back and then sends KDE's pointer-change
notification. A verified saved value and a sent notification do not prove how
every application renders the pointer. Themes may use a nearby size, and
already-open applications may need reopening. If notification fails, the saved
change remains verified and restorable; a profile stops before further changes.

Pointer size resets to Loofi's standard of 24. Theme controls have no Loofi
reset standard. A previous theme can be restored only while it remains installed.
Supported custom sizes from 0 to 512 are preserved exactly for readback and
history-based restoration; they are not offered as arbitrary new settings.

## Routine application and maintenance workflows

In Apps, open the Installed view and choose **Compare installations** on an app
with multiple known installations. Compare versions, format, installation scope
and reported sizes. App details and reviewed removal act on the exact selected
Flatpak installation and full ref. RPM management stays in the native software
manager. A matching name alone does not establish equivalence.

In Health, choose **Storage is full** and run the read-only check. Its storage
guide shows root, home and var measurements, cache and journal sizes, and unknown
measurements explicitly. Shared filesystem measurements are grouped rather than
summed. Review DNF cleanup separately, or choose a Flatpak installation and open
Apps to inspect unused runtimes. Journal retention remains manual guidance.
Reported sizes are not guaranteed savings. After a change, choose **Check again**.

In Updates, choose **Check restart advice** to read the local DNF5 recommendation.
Missing support or an inconsistent response stays unknown. Advice is held only
while this application runs and becomes stale after 24 hours. It does not restart
the computer or verify a saved Loofi update. Overview links select the relevant
source, saved operation or storage symptom; navigation never starts a check.

In the profile library, choose **Compare profiles**, then select the left and
right profiles for the same desktop. Differences describe saved target values,
not current computer settings. Edit a copy or start a fresh apply review for
either side through its separate button.

Read-only command-line counterparts:

```bash
loofi-fedora-tweaks --cli --json apps compare org.mozilla.firefox
loofi-fedora-tweaks --cli --json updates restart-advice
loofi-fedora-tweaks --cli --json tweaks profile library compare focus privacy-basics
```

See [Routine qualification](ROUTINE_VERIFICATION.md) for verified and remaining
physical checks.
