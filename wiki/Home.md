# Loofi Fedora Tweaks Wiki

Loofi Fedora Tweaks is a Fedora maintenance and desktop control center.

**Current release:** v22.0.0 "Alignment"<br>
**Supported target:** Fedora 44<br>
**Preview target:** Fedora 45

## What Alignment changes

- **Enforceable release trust:** COPR publication requires terminal API
  success, public repository metadata, and an exact clean-install readback.
- **Fedora-native handoffs:** Plasma-owned application and desktop settings
  open through fixed, non-privileged Discover and KDE KCM destinations.
- **Truthful capability states:** unavailable native tools stay explicit and
  never widen command or privilege authority.
- **Quieter workflows:** Home, Action Center, Specialist Tools, System Check,
  and Activity use one clearer local task hierarchy.
- **Stronger lifecycle and privacy:** bounded shutdown, structured Flatpak
  probes, RPM runtime dependencies, and credential redaction close trust gaps.
- **Compatibility preserved:** all 81 routes, aliases, favorites, state
  schemas, Traditional/Atomic policy, CLI, API, daemon, and IPC remain intact.

## Navigation

The unified shell has six destinations:

1. **Home** for current state, attention items, and common tasks.
2. **Software & Updates** for applications, repositories, updates, cleanup,
   Fedora upgrades, and Action Center.
3. **System** for system details, performance, processes, hardware, storage,
   diagnostics, health history, and recovery points.
4. **Network & Security** for connections, DNS, privacy, firewall, exposure,
   and backups.
5. **Desktop** for appearance, displays, and window behavior.
6. **Settings** for application behavior, Specialist Tools, Repair Loofi, and
   About.

Built-in specialist providers load only when opened through Specialist Tools,
search, favorites, or a stable deep link. Discoverability never changes
confirmation or privilege policy.

## Start here

- [Installation](Installation)
- [Getting Started](Getting-Started)
- [GUI Tabs Reference](GUI-Tabs-Reference)
- [CLI Reference](CLI-Reference)
- [Configuration](Configuration)
- [Security Model](Security-Model)
- [Atomic Fedora Support](Atomic-Fedora-Support)
- [Troubleshooting](Troubleshooting)

## Development

- [Architecture](Architecture)
- [Built-in Provider Development](Plugin-Development)
- [Contributing](Contributing)
- [Testing](Testing)
- [CI/CD Pipeline](CI-CD-Pipeline)
- [Changelog](Changelog)

## Release status

Alignment passed 6,909 tests, 61 expected skips, 1,079 subtests, and 86.65%
coverage, plus lint, typing, architecture, package, product-catalog, Wayland,
Orca/AT-SPI, GitHub provenance, COPR, and clean Fedora 44 install gates.
Fedora 45 remains preview-only.

- Repository: [loofiboss-bit/loofi-fedora-tweaks](https://github.com/loofiboss-bit/loofi-fedora-tweaks)
- Release: [v22.0.0 on GitHub](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v22.0.0)
- Release notes: [v22.0.0 release notes](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/releases/RELEASE-NOTES-v22.0.0.md)
- Fedora packages: [COPR](https://copr.fedorainfracloud.org/coprs/loofitheboss/loofi-fedora-tweaks/)
- Issues: [Issue tracker](https://github.com/loofiboss-bit/loofi-fedora-tweaks/issues)

For support, run `loofi-fedora-tweaks --cli doctor` and
`loofi-fedora-tweaks --cli support-bundle`, then include the Fedora variant,
exact route or command, reproduction steps, and relevant output in the issue.
