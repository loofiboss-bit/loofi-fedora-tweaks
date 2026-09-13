# Architecture — v27.0.1 "Core"

## Core purpose

Loofi Fedora Tweaks is a focused, desktop-neutral Fedora maintenance core. It
combines read-only inspection, capability-aware guidance, and reviewed
persistent changes without a background service or remote control plane.

## Product boundary

The supported product has five primary destinations:

1. **Home** — current state, one recommended next action, and common tasks.
2. **Updates & Apps** — system, host Flatpak, and firmware inspection, plus a
   native software-center handoff.
3. **System Health** — System Check, symptom troubleshooting, storage,
   hardware status, and support export.
4. **Protection & Recovery** — firewall exposure, backups, recovery points,
   exact backend-aware rollback guidance, and activity history.
5. **Changes** — the single review, confirmation, execution, and verification
   workspace for persistent changes.

Settings is a header-level route rather than a sixth primary destination.

## Platform profile

`core/platform/profile.py` owns the immutable `PlatformProfile`. It records
Fedora version, architecture, desktop, session, capabilities, reboot state,
and package/deployment backend. Supported backend values are `dnf5`,
`rpm_ostree`, `bootc`, and `unknown`. Detection is capability-first and
fail-closed: unknown data never becomes a Traditional, Workstation, KDE, or
“no reboot required” assumption.

The same profile is passed to navigation, readiness, Action Center eligibility,
native handoffs, update inspection, and support evidence. A backend-specific
operation is unavailable unless its capability and verification path are
known.

## Execution and trust boundary

All persistent host mutations enter the Action Center as closed action
definitions and typed parameters. The lifecycle is:

`request → plan → fresh preflight → explicit confirmation → bounded execute →
independent verify → typed outcome`.

UI code does not import mutating services or execute subprocesses. CLI handlers
serialize domain results and never accept arbitrary command vectors, shell
fragments, unattended schedules, or implicit confirmation. Native authorization
is requested only for the reviewed operation that needs it.

## Public interfaces and distribution

The public entry modes are the PyQt6 GUI and the reduced CLI (`info`, `check`,
`updates`, `troubleshoot`, `changes`, `activity`, `doctor`, and
`support-bundle`). The supported distribution is one COPR-backed RPM, with an
sdist for development. The Core release does not ship the local Web API,
D-Bus daemon, specialist suites, custom Polkit policy files, or a Flatpak
application bundle.

## Testing contract

The full deterministic test suite runs compatibility modules as well as the
maintained surface. v27.0.1 uses an 85% blocking coverage gate for the
maintained Fedora Maintenance Core and measured 86.95% locally. The
repository-wide 90% target is explicitly deferred to the next release.

Physical desktop, authorization-agent, reboot, fresh Atomic, manual keyboard,
and audible Orca qualification are separate evidence gates. They remain
`unverified` for v27.0.1 under the authorized manual-test skip and must never
be inferred from rootless or offscreen runs.
