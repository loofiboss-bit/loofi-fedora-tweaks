# Loofi Fedora Tweaks 32.4.0 — Care

Care adds clearer installed-app details, storage insight, safer Flatpak runtime
cleanup, and source-specific update diagnostics to the Fedora desktop control
center.

## Highlights

- Inspect an installed app's version, installation scope, source, exact Flatpak
  ref, runtime, reported size, and locally recorded app or runtime end-of-life
  information.
- Filter installed apps by source and installation, then sort by name or
  reported size. Unknown sizes stay visible and sort last.
- Review unused runtimes for one Flatpak installation and remove only the exact
  reviewed refs through Action Center. A changed inventory requires a new
  review; app data is preserved and partial outcomes are reported.
- Diagnose failed System, Flatpak, or Firmware update checks with bounded,
  read-only source observations and links to the recorded operation.
- Keep GUI and CLI update status aligned, including when a source check fails.
- Include reviewed desktop presets, installation-bound permission details,
  search, accessibility, and responsive-layout improvements.

## Safety and storage notes

Reported app sizes are installation-reported values. Flatpak objects can be
shared, so a size is not a promise of reclaimed disk space. The absence of a
locally recorded end-of-life warning is not a support guarantee. System and
named Flatpak installations are shared; cleanup inspection does not inspect
other users' private app inventories. PyGObject and libflatpak are optional;
the application does not install them automatically.

## Install

Download the RPM asset from this release and install it with:

```bash
pkexec dnf install ./loofi-fedora-tweaks-32.4.0-*.noarch.rpm
```

Or install from the Loofi COPR repository:

```bash
pkexec dnf copr enable loofitheboss/loofi-fedora-tweaks
pkexec dnf install loofi-fedora-tweaks
```

## Qualification

Automated verification passed with 4,888 tests, 33 skipped, 1,961 subtests,
and 85.27% coverage. Packaging and isolated Flatpak cleanup fixtures passed.
See [Care qualification](../CARE_VERIFICATION.md) for the detailed evidence.
Physical KDE/GNOME behavior, screen-reader use, and interactive Polkit prompts
remain unverified.
