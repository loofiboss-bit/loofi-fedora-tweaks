# Loofi Fedora Tweaks Wiki

Loofi Fedora Tweaks is a Fedora maintenance and desktop control center.

**Candidate:** v18.0.0 "Haven"<br>
**Supported target:** Fedora 44<br>
**Preview target:** Fedora 45

## What Haven changes

- **One product catalog:** 80 stable routes project from reviewed, data-only
  metadata while retaining their existing IDs and aliases.
- **One host-change boundary:** 56 first-party Action Center definitions state
  their operation class, Fedora variants, reboot policy, affected resources,
  preflight, confirmation, verification, and recovery policy.
- **No unattended host changes:** daemon, scheduler, automation, and agent paths
  may create plans but cannot confirm or execute them.
- **Schema v3:** writable Action Center v1/v2 state migrates atomically; unknown
  future schemas remain read-only.
- **Local profiles:** explicit JSON profiles remain data-only and become
  reviewable plans before host settings change.
- **No executable third-party plugins:** the public Marketplace and external
  Python loading are retired. Existing extension files remain untouched and can
  be inventoried or exported.
- **Local secrets:** Gist and JWT secrets use Secret Service when available,
  with session-only fallback. The optional Web API accepts loopback bindings
  only.

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

The Haven candidate passed the local suite with 6,796 tests, 68 skipped, and
86.24% coverage. Meaningful Home measured 142.042 ms median and 75,408 KiB
median RSS. Historical Sentinel is preserved as
`legacy-v18.0.0-sentinel`. Canonical CodeQL, the Haven tag, GitHub assets, and
COPR publication remain pending.

- Repository: [loofiboss-bit/loofi-fedora-tweaks](https://github.com/loofiboss-bit/loofi-fedora-tweaks)
- Candidate notes: [v18.0.0 release notes](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/releases/RELEASE-NOTES-v18.0.0.md)
- Issues: [Issue tracker](https://github.com/loofiboss-bit/loofi-fedora-tweaks/issues)

For support, run `loofi-fedora-tweaks --cli doctor` and
`loofi-fedora-tweaks --cli support-bundle`, then include the Fedora variant,
exact route or command, reproduction steps, and relevant output in the issue.
