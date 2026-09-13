# Loofi Fedora Tweaks Wiki

Loofi Fedora Tweaks is a focused, desktop-neutral Fedora maintenance core.

**Current release:** v27.0.1 "Core"<br>
**Stable targets:** Fedora 43 and 44<br>
**Preview target:** Fedora 45

## What Loofi does

- Troubleshooting starts only when you choose a symptom and begin.
- Supported system changes become reviewed Action Center plans before anything
  is applied.
- Maintenance outcomes are verified separately from command completion.
- Traditional and Atomic Fedora paths remain distinct.
- Desktop-neutral core operating across all official Fedora desktop environments.

## Navigation

The unified shell has five destinations:

1. **Home** for system state, single recommended action, and common tasks.
2. **Updates & Apps** for system, Flatpak, and firmware updates, and neutral app handoff.
3. **System Health** for System Check, symptom troubleshooting, storage, hardware, and support bundle.
4. **Protection & Recovery** for firewall, exposure, backups, exact rollbacks, and activity.
5. **Changes** for the Action Center review and verification workspace.

The v27 core has no separate specialist product, executable extension system,
background daemon, web API, or Flatpak application bundle. Flatpak remains an
optional host update source inside **Updates & Apps**.

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

v27.0.1 "Core" is the current public release. v26.0.3 "Everyday" is the
previous public release. Automated rootless/offscreen qualification passed;
physical desktop and keyboard use, accessibility, Polkit, reboot, and fresh
Atomic qualification remain unverified by the explicit release decision.
Fedora 45 remains preview-only.

- Repository: [loofiboss-bit/loofi-fedora-tweaks](https://github.com/loofiboss-bit/loofi-fedora-tweaks)
- Release notes: [v27.0.1 Core](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/releases/RELEASE-NOTES-v27.0.1.md)
- Release: [v26.0.3 on GitHub](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v26.0.3)
- Release notes: [v26.0.3 release notes](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/releases/RELEASE-NOTES-v26.0.3.md)
- Fedora packages: [COPR](https://copr.fedorainfracloud.org/coprs/loofitheboss/loofi-fedora-tweaks/)
- Issues: [Issue tracker](https://github.com/loofiboss-bit/loofi-fedora-tweaks/issues)

For support, run `loofi-fedora-tweaks --cli doctor` and
`loofi-fedora-tweaks --cli support-bundle`, then include the Fedora variant,
exact route or command, reproduction steps, and relevant output in the issue.
