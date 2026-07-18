# Loofi Fedora Tweaks v15.0.0 "Essentials" Release Announcement

## TL;DR

Essentials gives Loofi Fedora Tweaks a smaller, faster default experience: six
destinations, one Home, one search surface, and Standard or Advanced mode. The
v14 Action Center, state integrity, Fedora safety, routes, CLI, API, and daemon
contracts remain intact.

Publication is pending exact release-tag lineage and the remaining remote
release gates. This file is the prepared announcement, not a claim that v15 is
already live.

## Highlights

- Six Standard destinations: Home, Software & Updates, System, Network &
  Security, Desktop, and Settings.
- One optional Advanced destination for specialist tools.
- One read-only Home and one policy-backed route/settings/action search surface.
- Meaningful Home measured 96.66% faster with 29.20% lower RSS than the recorded
  v14 baseline.
- Five clearer workflows for updates, application installation, slow-system
  diagnosis, disk reclaim analysis, and recovery protection.
- Logical core/specialist isolation without an unsafe physical RPM split.
- The verified Action Center remains explicit, plan-based, deny-by-default, and
  separately verified.

## Install or upgrade

After the release is published:

```bash
pkexec dnf copr enable loofitheboss/loofi-fedora-tweaks
pkexec dnf upgrade loofi-fedora-tweaks
```

Optional runtimes remain separate:

```bash
pkexec dnf install loofi-fedora-tweaks-api
pkexec dnf install loofi-fedora-tweaks-daemon
```

## Links

- **Release notes**: `docs/releases/RELEASE-NOTES-v15.0.0.md`
- **Changelog**: `CHANGELOG.md`
- **Architecture**: `ARCHITECTURE.md`
- **Issue tracker**: <https://github.com/loofiboss-bit/loofi-fedora-tweaks/issues>

The GitHub release URL will be
<https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v15.0.0>
after exact-lineage publication succeeds.
