# Atomic Fedora Support — v27.0.1 "Core"

Loofi detects Fedora deployment capability before presenting an operation. The
profile distinguishes `rpm_ostree`, `bootc`, traditional `dnf5`, and
`unknown`; it never treats an unknown host as a different backend.

## What the application does

- Shows the deployment backend and reboot state in read-only diagnostics.
- Keeps Atomic and traditional update paths separate.
- Presents a reviewable Action Center plan only when preflight, authorization,
  verification, and recovery metadata are known.
- Leaves staged-deployment reboot completion to the user's normal desktop
  controls, followed by an explicit verification step.
- Hands unsupported or backend-specific work to a clear manual explanation.

## Safe workflow

1. Run `loofi-fedora-tweaks --cli --json info` and inspect the profile.
2. Run `loofi-fedora-tweaks --cli updates check` or open **Updates & Apps**.
3. Review any plan in **Changes** before confirmation.
4. After a host-managed restart, run `loofi changes verify <RUN_ID>`.

Loofi does not run `systemctl reboot`, retry a failed transaction, schedule a
deployment, or silently add a repository/remote.

## Backend notes

`rpm_ostree` and bootc deployments may stage a new deployment and require a
restart. DNF history operations are not assumed to exist on Atomic hosts.
bootc hosts are not routed through rpm-ostree commands. If detection is
incomplete, update and rollback actions are shown as unavailable rather than
guessing.

## Qualification boundary

Silverblue, Kinoite, and other Atomic variants are supported as a capability-
aware product path, but a fresh Atomic install and physical reboot completion
were not manually qualified for v27.0.1. Those gates remain **unverified** by
the explicit release decision. Rootless/offscreen tests do not replace them.

For current behavior, see [Verified Maintenance](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/VERIFIED_MAINTENANCE.md)
and [Troubleshooting](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/TROUBLESHOOTING.md).
