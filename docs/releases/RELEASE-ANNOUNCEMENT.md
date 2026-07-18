# Loofi Fedora Tweaks v16.0.0 "Clarity" Release Announcement

## TL;DR

Clarity gives Loofi Fedora Tweaks one responsive shell and one consistent page
language. Full-label section navigation, shared components, semantic themes,
and accessible focus behavior now cover Standard and Advanced without changing
trusted system operations.

The release is live on GitHub and the Fedora 44 COPR repository. Checksums,
CycloneDX SBOM, in-toto/SLSA provenance, RPMs, Flatpak, and source distribution
were read back and verified against the exact release commit.

## Highlights

- Responsive section rails collapse to a compact selector on small windows.
- All six Standard destinations and Advanced use the shared page scaffold,
  cards, actions, states, and spacing.
- System, dark, light, and high-contrast themes keep structural styling.
- The real shell passed 400 automated layout/theme/font cells plus live Wayland,
  Qt `xcb`, keyboard, contrast, and AT-SPI validation.
- Meaningful Home remains within the same-host release budget with one startup
  plugin and no startup probes, active timers, or worker threads.
- Routes, state, Action Center, Fedora variants, CLI, API, daemon, and IPC remain
  compatible.

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

- **GitHub release**: <https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v16.0.0>
- **Release notes**: <https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/releases/RELEASE-NOTES-v16.0.0.md>
- **COPR packages**: <https://copr.fedorainfracloud.org/coprs/loofitheboss/loofi-fedora-tweaks/>
- **Wiki**: <https://github.com/loofiboss-bit/loofi-fedora-tweaks/wiki>
- **Issue tracker**: <https://github.com/loofiboss-bit/loofi-fedora-tweaks/issues>
