# Loofi Fedora Tweaks Wiki

Loofi Fedora Tweaks is a Fedora maintenance and desktop control center.

**Current release:** v20.0.0 "Continuity"<br>
**Supported target:** Fedora 44<br>
**Preview target:** Fedora 45

## What Continuity changes

- **Trusted activity:** one privacy-bounded journal composes Action Center,
  DNF5, rpm-ostree, Flatpak, fwupd, and Loofi records without a new database.
- **Conservative recovery:** only exact DNF5 install/remove transactions and
  exact rpm-ostree deployment rollbacks can create recovery plans.
- **Action Center remains authoritative:** recovery creates a plan and still
  requires separate confirmation, execution, and verification.
- **Unified navigation:** Specialist Tools are always discoverable without a
  global Standard/Advanced safety switch.
- **Compatibility preserved:** stable routes, aliases, favorites, state
  schemas, System Check, CLI, API, daemon, and IPC remain intact.

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

Continuity passed 6,822 tests, 68 expected skips, 1,057 subtests, and 86.10%
coverage, plus lint, typing, architecture, package, product-catalog, and
offscreen UI gates. The historical Synapse lineage is preserved as
`legacy-v20.0.0-synapse`.

- Repository: [loofiboss-bit/loofi-fedora-tweaks](https://github.com/loofiboss-bit/loofi-fedora-tweaks)
- Release notes: [v20.0.0 release notes](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/releases/RELEASE-NOTES-v20.0.0.md)
- Issues: [Issue tracker](https://github.com/loofiboss-bit/loofi-fedora-tweaks/issues)

For support, run `loofi-fedora-tweaks --cli doctor` and
`loofi-fedora-tweaks --cli support-bundle`, then include the Fedora variant,
exact route or command, reproduction steps, and relevant output in the issue.
