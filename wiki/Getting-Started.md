# Loofi Fedora Tweaks — Getting Started

> Version 30.1.0 "Personalize" release; physical desktop validation remains pending.

<!-- Canonical source mirrored byte-for-byte to wiki/Getting-Started.md. -->

Use this guide for a safe first run in under 10 minutes.

## 1) Install and launch

```bash
pkexec dnf copr enable loofitheboss/loofi-fedora-tweaks
pkexec dnf install loofi-fedora-tweaks
loofi-fedora-tweaks
```

The first launch opens Home. Browsing a page does not modify the host. Loofi
checks availability before it offers an executable operation, and unknown
deployment backends remain unavailable.

## 2) Learn the five destinations

1. **Home** — Fedora profile, current status, one recommended next step, and
   shortcuts to everyday jobs.
2. **Apps** — search the curated application catalog, filter by category,
   select several applications, and review each source.
3. **Tweaks** — search settings, choose a value, and see the verified result
   on the same row.
4. **Health** — choose the symptom you recognise, inspect the findings, and use
   one supported repair, instruction, or native-settings handoff.
5. **Updates** — check System, Flatpak, and Firmware independently and follow
   the single action shown on each card.

Activity & Recovery and Settings are opened from the header. The internal
execution engine is not a destination and is not required terminology for
normal work.

## 3) Complete common jobs

### Install several applications

Open **Apps**, search or choose a category, select the applications, and
choose **Review selected applications**. Confirm the source summary. Each item
keeps its own result, so one failed installation does not hide the others.

### Change a desktop setting

Open **Tweaks**, search for a setting, and choose a value. The row shows the
current value and confirms it after an independent readback. Custom KDE values
stay visible until you deliberately choose another value.

### Diagnose a problem

Open **Health**, choose the symptom, and start the read-only diagnosis. Loofi
shows findings before offering one next step. There is no global **Fix all**.

### Update Fedora

Open **Updates**. Each source shows one button: **Check**, **Update**,
**Continue**, or **Verify**. A reboot-required result stays in Activity &
Recovery until you return and verify it.

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
