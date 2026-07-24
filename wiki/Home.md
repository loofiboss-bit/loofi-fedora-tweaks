# Loofi Fedora Tweaks Wiki

Loofi Fedora Tweaks is a Fedora maintenance and desktop control center.

**Current release:** v19.0.0 "Steward"<br>
**Supported target:** Fedora 44<br>
**Preview target:** Fedora 45

## What Steward changes

- **Guided health journey:** one explicit System Check path from Home to the
  canonical diagnostics workflow, with no cold-start probe and no polling.
- **Structured findings and actions:** reusable finding evidence moves to
  Action Center through audited handoff only, with closed verification data.
- **Read-only and cancellable checks:** System Check operations are bounded,
  timeout-aware, and can be cancelled and recovered.
- **Separation of concerns:** host mutations still pass through Action Center
  plan/apply confirmation; System Check itself is read-only.
- **Compatibility preserved:** health/timeline aliases, favorites, saved
  navigation, existing CLI compatibility routes, and unknown future schema behavior
  remain intact.

## Navigation

Standard mode has six destinations:

1. **Home** for current state, attention items, and common tasks.
2. **Software & Updates** for applications, repositories, updates, cleanup,
   Fedora upgrades, and Action Center.
3. **System** for system details, performance, processes, hardware, storage,
   diagnostics, health history, and recovery points.
4. **Network & Security** for connections, DNS, privacy, firewall, exposure,
   and backups.
5. **Desktop** for appearance, displays, and window behavior.
6. **Settings** for application behavior, Advanced mode, Repair Loofi, and
   About.

Built-in specialist providers load only when opened through Advanced mode,
search, favorites, or a stable deep link. Advanced mode changes discovery, not
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

Steward is currently at release-candidate status with local verification complete:
6,882 tests, 68 skipped, 1,032 subtests passed, and 86.26% coverage.
Meaningful Home measured 160.661 ms median and 76,048 KiB median RSS. The
verified payload includes startup, startup duration, and System Check timing gates,
bandit, dependency checks, and packaging builds. Publication to GitHub release,
COPR, and signed provenance is pending explicit authorization.
Historical Sentinel is preserved as `legacy-v18.0.0-sentinel`.

- Repository: [loofiboss-bit/loofi-fedora-tweaks](https://github.com/loofiboss-bit/loofi-fedora-tweaks)
- Release notes: [v19.0.0 release notes](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/releases/RELEASE-NOTES-v19.0.0.md)
- Issues: [Issue tracker](https://github.com/loofiboss-bit/loofi-fedora-tweaks/issues)

For support, run `loofi-fedora-tweaks --cli doctor` and
`loofi-fedora-tweaks --cli support-bundle`, then include the Fedora variant,
exact route or command, reproduction steps, and relevant output in the issue.
