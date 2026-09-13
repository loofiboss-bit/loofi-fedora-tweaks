# Loofi Fedora Tweaks Wiki

Loofi Fedora Tweaks is a Fedora maintenance and desktop control center.

**Candidate:** v27.0.0 "Core"<br>
**Supported targets:** Fedora 43 and 44<br>
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

Proof is the current public release. Its rootless/offscreen qualification and
public publication evidence are reported separately. Physical Fedora KDE,
keyboard, accessibility, reboot, and manual recovery gates remain unverified.
The public baseline remains v24.0.0 "Flow", whose historical release evidence
is preserved separately. Fedora 45 remains preview-only.

- Repository: [loofiboss-bit/loofi-fedora-tweaks](https://github.com/loofiboss-bit/loofi-fedora-tweaks)
- Release notes: [v25.0.4 Proof](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/releases/RELEASE-NOTES-v25.0.4.md)
- Release: [v24.0.0 on GitHub](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v24.0.0)
- Release notes: [v24.0.0 release notes](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/releases/RELEASE-NOTES-v24.0.0.md)
- Fedora packages: [COPR](https://copr.fedorainfracloud.org/coprs/loofitheboss/loofi-fedora-tweaks/)
- Issues: [Issue tracker](https://github.com/loofiboss-bit/loofi-fedora-tweaks/issues)

For support, run `loofi-fedora-tweaks --cli doctor` and
`loofi-fedora-tweaks --cli support-bundle`, then include the Fedora variant,
exact route or command, reproduction steps, and relevant output in the issue.
