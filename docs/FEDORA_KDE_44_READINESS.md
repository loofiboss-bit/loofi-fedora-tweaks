# Historical Fedora KDE 44 Readiness Note — v30.0.1 "Steady"

This v30.0.1 local candidate retains a Fedora-neutral readiness model; this
filename is retained for links from earlier releases. It is not a KDE 44
product gate. The model uses the immutable `PlatformProfile`, probes
desktop-specific checks only when the detected desktop requires them, and
keeps unknown values unavailable.

Use the maintained documentation instead:

- [Verified Maintenance](VERIFIED_MAINTENANCE.md) for read-only checks and the
  shared verified operation model.
- [Troubleshooting](TROUBLESHOOTING.md) for bounded diagnostic sessions.
- [Release Checklist](RELEASE_CHECKLIST.md) for automated release gates and
  supplementary physical qualification evidence.

The supported public CLI is deliberately limited to eight commands:
`info`, `check`, `updates`, `troubleshoot`, `changes`, `activity`, `doctor`,
and `support-bundle`. Historical readiness, daemon, API, and KDE-specific
command examples are not part of the v29.0.1 product contract and must not be
copied into new guides.

Physical desktop, reboot, authorization, and Atomic/bootc qualification remain
`unverified` until the corresponding matrix is run on real Fedora hosts.
