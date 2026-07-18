# Loofi Fedora Tweaks v15.0.0 "Essentials" Release Announcement

## TL;DR

Essentials gives Loofi Fedora Tweaks a smaller, faster default experience: six
destinations, one Home, one search surface, and Standard or Advanced mode. The
v14 Action Center, state integrity, Fedora safety, routes, CLI, API, and daemon
contracts remain intact.

The release is live on GitHub and the Fedora 44 COPR repository. Checksums,
CycloneDX SBOM, in-toto/SLSA provenance, RPMs, Flatpak, and source distribution
were read back and verified against the exact release commit.

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

- **GitHub release**: <https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v15.0.0>
- **Release notes**: <https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/releases/RELEASE-NOTES-v15.0.0.md>
- **COPR packages**: <https://copr.fedorainfracloud.org/coprs/loofitheboss/loofi-fedora-tweaks/>
- **Wiki**: <https://github.com/loofiboss-bit/loofi-fedora-tweaks/wiki>
- **Issue tracker**: <https://github.com/loofiboss-bit/loofi-fedora-tweaks/issues>
