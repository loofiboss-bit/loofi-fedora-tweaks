# Loofi Fedora Tweaks — Getting Started

> v33.0.1 Concord guide updated 2026-10-12; physical desktop and assistive-technology validation remains a separate qualification.

<!-- Canonical source mirrored byte-for-byte to wiki/Getting-Started.md. -->

Use this guide for a safe first run in under 10 minutes.

## 1) Install and launch

```bash
pkexec dnf copr enable loofitheboss/loofi-fedora-tweaks
pkexec dnf install loofi-fedora-tweaks
loofi-fedora-tweaks
```

The first launch opens **Overview**, a read-only system dashboard. If reopening
the last page is enabled, later launches return to that page. Browsing a page
does not modify the host. Loofi
checks availability before it offers an executable operation, and unknown
deployment backends remain unavailable.

## 2) Learn the six destinations

1. **Overview** — start with CPU, RAM, GPU, and storage, then review recorded
   next steps, update/Health history, guides, and recent changes.
2. **Tweaks** — use Settings or Profiles, search a setting, choose a value, and see the verified result
   on the same row. **Restore previous value** recovers an eligible recorded
   value; **Use Loofi standard value** applies Loofi's curated reference.
3. **Apps** — use Catalog, Installed, or Sources; search the curated catalog, filter by category,
   select several applications, and review each source and installation scope.
4. **Updates** — check System, Flatpak, and Firmware independently and follow
   the single action shown in each section.
5. **Health** — choose the symptom you recognise, inspect findings, and review
   one supported repair, instruction, or native-settings handoff.
6. **Activity** — inspect recorded changes, verification results, and available
   recovery or reboot follow-up.

Expand **Tools** in the sidebar for System, Storage, Network, Security, and
Logs. The group starts collapsed; an existing advanced-tools preference is
retained. **Settings** is at the bottom of the sidebar. Global search is in the
header; `Ctrl+K` opens it and selecting a result navigates without applying a
change.

Overview explains **Collecting**, **Unavailable**, **Read failed**, and **Last
known value** instead of reporting missing measurements as zero. Hover a metric
for its source and measurement time. Measurements pause when no measurement
page is visible or the window is hidden/minimized. **Pause** keeps the last
measurements visible; **Resume** starts a fresh sampling baseline. Missing
hardware, including a battery, is stated explicitly.

The first-run card and **Guides** panel are optional. Dismiss the card when it
is no longer useful, or reopen it later with **Show introduction**. Guide
progress can be resumed. Missing update results are **Not checked** or
unavailable, not a verified zero. Saved symptom diagnoses show whether
collection was complete or partial and remain separate from System Check.

## 3) Complete common jobs

### Install several applications

Open **Apps**, search or choose a category, select the applications, and
choose **Review selected applications**. Confirm the source summary. Each item
keeps its own result, so one failed installation does not hide the others.
If the catalog has no match, open Discover or GNOME Software to browse there.
For RPM apps, Loofi names the exact package before opening the native software
manager; return and refresh the installed-app list to see the resulting state.

### Change a desktop setting

Open **Tweaks**, search for a setting, and choose a value. The row shows the
current value and confirms it after an independent readback. Custom KDE values
stay visible until you deliberately choose another value. GNOME Files offers
single/double-click opening and a default folder view. KDE adds Dolphin's full
path display and KWin's maximized titlebar behavior. A saved KDE setting may
require reopening affected applications.

Use **Restore previous value** to review and confirm the latest eligible Loofi
change. External changes, later attempts, missing history, and removed choices
block restoration. A successful restore is separately verified and consumes
the offer.
The **Changed** filter compares values with Loofi's curated standard, not the
desktop's default. After a long or cancelled current-state check, choose
**Check remaining settings** to continue with skipped values; **Refresh** checks
the full catalog again.

### Diagnose a problem

Open **Health**, choose the symptom, and start the read-only diagnosis. Loofi
shows findings before offering one next step. There is no global **Fix all**.

### Update Fedora

Open **Updates**. Each source shows one button: **Check**, **Update**,
**Continue**, or **Verify**. A reboot-required result stays in
Activity until you return and verify it.

## 4) Optional CLI

```bash
alias loofi='loofi-fedora-tweaks --cli'

loofi info
loofi check
loofi updates check
loofi troubleshoot profiles
loofi activity list
loofi doctor
loofi support-bundle
```

`changes` remains a v29 compatibility alias for Activity list/detail and for
explicit completion of older saved plans. Add `--json` before a command for
machine-readable output.

## 5) Next docs

- [Full user guide](../docs/USER_GUIDE.md)
- [Verified operations](../docs/VERIFIED_MAINTENANCE.md)
- [State integrity](../docs/STATE_INTEGRITY.md)
- [Troubleshooting](../docs/TROUBLESHOOTING.md)
- [Documentation index](../README.md)
