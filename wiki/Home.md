# Loofi Fedora Tweaks Wiki

Loofi Fedora Tweaks is a Fedora maintenance and desktop control center.

**Current release:** v23.0.2 "Compass"<br>
**Supported target:** Fedora 44<br>
**Preview target:** Fedora 45

## What Loofi does

- Troubleshooting starts only when you choose a symptom and begin.
- Supported system changes become reviewed Action Center plans before anything
  is applied.
- Maintenance outcomes are verified separately from command completion.
- Traditional and Atomic Fedora paths remain distinct.
- The optional API is loopback-only and cannot apply plans.

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

## Current guides

- [Getting Started](Getting-Started)
- [Screenshots](Screenshots)
- [User guide](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/USER_GUIDE.md)
- [Verified maintenance](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/VERIFIED_MAINTENANCE.md)
- [Troubleshooting](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/TROUBLESHOOTING.md)
- [Advanced administration](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/ADVANCED_ADMIN_GUIDE.md)
- [Documentation index](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/README.md)
- [Contributing](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/CONTRIBUTING.md)

Older standalone wiki pages remain available as historical material. The
repository guides linked above are the current usage and development sources.

## Release status

Compass's final Fedora 44 qualification passed 7,007 tests, 61 expected skips,
1,184 subtests, and 86.26% coverage. Exact-tag GitHub CI and CodeQL, eight
release assets, checksums, SBOM, provenance, attestations, COPR build
`10788467`, signed packages, a clean Fedora 44 install, and a real Fedora 44
host daemon readback passed. Fresh Atomic/Kinoite and manual keyboard/audible
Orca journeys remain explicitly unverified under an authorized skip. Fedora
45 remains preview-only.

- Repository: [loofiboss-bit/loofi-fedora-tweaks](https://github.com/loofiboss-bit/loofi-fedora-tweaks)
- Release: [v23.0.2 on GitHub](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v23.0.2)
- Release notes: [v23.0.2 release notes](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/releases/RELEASE-NOTES-v23.0.2.md)
- Fedora packages: [COPR](https://copr.fedorainfracloud.org/coprs/loofitheboss/loofi-fedora-tweaks/)
- Issues: [Issue tracker](https://github.com/loofiboss-bit/loofi-fedora-tweaks/issues)

For support, run `loofi-fedora-tweaks --cli doctor` and
`loofi-fedora-tweaks --cli support-bundle`, then include the Fedora variant,
exact route or command, reproduction steps, and relevant output in the issue.
