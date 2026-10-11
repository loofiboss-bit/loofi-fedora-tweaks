# Guide 32.8.0 — published

Loofi Fedora Tweaks 32.8.0 “Guide” is a published release. Its four resumable
workflows help users make Fedora theirs, choose and manage apps, maintain the
system, and solve a problem. Guide search and saved local progress make these
workflows discoverable and resumable; the CLI can inspect available guides.

Opening a guide step routes to the relevant existing page or review surface. It
does not start a check or change. Any result shown as verified must come from a
referenced successful operation.

This release continues to prioritize KDE and traditional Fedora with DNF5.
GNOME and Atomic qualification boundaries remain specific to the features
covered by the available evidence.

## Qualification record

The [Guide verification report](../GUIDE_VERIFICATION.md) records automated,
packaging, installed-RPM, and offscreen-rendering checks performed for the
32.8.0 release on 2026-10-11. It is historical evidence for that release.
It does not qualify subsequent stabilization or UX changes. The report also
lists physical KDE interactions that were not tested at that time.

## Installation

```bash
pkexec dnf install ./loofi-fedora-tweaks-*.rpm
```

See the [changelog](../../CHANGELOG.md) for the release history and the
[roadmap](../../ROADMAP.md) for planned follow-up work.
