# Loofi Fedora Tweaks Wiki

Loofi Fedora Tweaks is a Fedora maintenance and desktop control center.

**Current release:** v21.0.0 "Resolve"<br>
**Supported target:** Fedora 44<br>
**Preview target:** Fedora 45

## What Resolve changes

- **Guided work:** Home presents one truthful summary and one primary next step
  over the existing safe routes and state.
- **Explicit review:** application install and removal hand off to Action
  Center before confirmation and execution.
- **State-driven detail:** System Check and Activity & Recovery show local
  views only when their current state supports them.
- **Deterministic teardown:** application-owned timers, workers, schedulers,
  subscriptions, Pulse, and plugins stop with the shell.
- **Responsive navigation:** compact, scaled, RTL, Wayland, X11, keyboard, and
  assistive-technology layouts preserve all stable routes.
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

Resolve passed 6,863 tests, 61 expected skips, 1,057 subtests, and 86.57%
coverage, plus lint, typing, architecture, package, product-catalog, and
offscreen UI gates. The historical occupied v21 lineages are preserved as
`legacy-v21.0.0-ux-stabilization` and
`legacy-v21.0.1-python-jose-packaging`.

- Repository: [loofiboss-bit/loofi-fedora-tweaks](https://github.com/loofiboss-bit/loofi-fedora-tweaks)
- Release: [v21.0.0 on GitHub](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v21.0.0)
- Release notes: [v21.0.0 release notes](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/releases/RELEASE-NOTES-v21.0.0.md)
- Fedora packages: [COPR](https://copr.fedorainfracloud.org/coprs/loofitheboss/loofi-fedora-tweaks/)
- Issues: [Issue tracker](https://github.com/loofiboss-bit/loofi-fedora-tweaks/issues)

For support, run `loofi-fedora-tweaks --cli doctor` and
`loofi-fedora-tweaks --cli support-bundle`, then include the Fedora variant,
exact route or command, reproduction steps, and relevant output in the issue.
