# Loofi Fedora Tweaks 35.0.0 “Everyday”

Everyday brings application management, optional first-run setup and reliable
operation results together for traditional Fedora KDE with DNF5.

## Highlights

- Search local AppStream catalogs alongside curated recommendations. Choose
  RPM or Flatpak, actual source and installation explicitly. Missing metadata
  stays unavailable; catalog package updates receive a separate RPM review.
- Review complete RPM installation and removal transactions, including exact
  package versions, architectures, sources and dependency changes. Protected
  system components cannot be removed, and changed evidence needs a new review.
- Install Flatpaks and update selected installed applications with exact
  installation, remote, commit and resolved dependency verification.
- Use the optional **Get Fedora ready** guide. Separately review Flathub,
  RPM Fusion Free/Nonfree and the fixed FFmpeg/GStreamer codec recipe. Nothing
  is preselected; codec replacements require separate removal consent.
- See consistent interrupted, partial, unknown and verified results across
  Overview, Updates and Activity. Result rechecks never replay a mutation.
- Resume guides with verified result links and preserved backup/profile/history
  compatibility. Backup acknowledgement remains a user task.

## Validation and known limitations

Local verification passed 5,674 tests with 85.38% maintained coverage, packaging
checks and an RPM build. Search p95 was 52.70 ms in the 500-row fixture; paired
startup was +3.81%. The canonical release workflow records its own source,
build, installed-package and publication results.

Qt's scroll-area accessibility defect remains reproducible with the installed
Fedora Qt runtime. An isolated corrected QtWidgets build passes the native
regression, but that library is not included in the application RPM. Accessibility
remains enabled. Full candidate X11/Wayland, AT-SPI and offline-reboot matrices
are not qualified; fresh guest provisioning timed out before candidate tests.
These are disclosed limitations under the maintainer's risk-based release policy,
with native matrices available as optional manual workflow inputs.

GNOME and Atomic retain existing capability boundaries. Fedora version upgrades
remain preparation and guidance. Permission editing, automatic repair,
unattended updates and general system recovery are outside this release.

See [qualification details](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/v35.0.0/docs/V35_QUALIFICATION.md)
and the [changelog](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/v35.0.0/CHANGELOG.md).

## Install

Use the Fedora 44 COPR channel, or download the RPM and checksums from this release:

```bash
pkexec dnf copr enable loofitheboss/loofi-fedora-tweaks
pkexec dnf install loofi-fedora-tweaks
```

Launch the application as your normal desktop user. Reviewed system changes
request authorization through the desktop Polkit agent.
