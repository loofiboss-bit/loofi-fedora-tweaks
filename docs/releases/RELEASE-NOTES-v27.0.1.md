# v27.0.1 "Core" — Fedora Maintenance Core

**Release date:** 2026-09-13  
**Codename:** Core

## Summary

v27.0.1 makes Loofi Fedora Tweaks a smaller, desktop-neutral Fedora
maintenance core. The product now has five destinations, one Action Center
for persistent changes, capability-aware platform detection, and a native
software-center handoff instead of a second application marketplace.

This is the unambiguous Core release identity. The historical `v27.0.0`
Marketplace Enhancement tag is preserved unchanged; this release uses
`v27.0.1` for the reviewed Core implementation.

## Highlights

- Home, Updates & Apps, System Health, Protection & Recovery, and Changes are
  the five primary destinations.
- An immutable `PlatformProfile` describes Fedora version, architecture,
  desktop, session, capabilities, and deployment backend (`dnf5`,
  `rpm_ostree`, `bootc`, or `unknown`). Unknown values fail closed.
- Every supported persistent mutation is reviewed, explicitly confirmed, and
  verified through the Action Center. No automatic reboot, retry, rollback, or
  unattended scheduling is performed.
- Applications are handed to the installed native software center through a
  desktop-neutral AppStream/XDG link. Loofi does not mirror or mutate an app
  catalogue.
- The public CLI is reduced to `info`, `check`, `updates`, `troubleshoot`,
  `changes`, `activity`, `doctor`, and `support-bundle`.

## Decommissioned public surfaces

The Core product no longer ships specialist suites, the local Web API, a
D-Bus/background daemon, a Flatpak application bundle, custom marketplace
operations, generic schedules, or dead-end “rollback last update” actions.
Host Flatpak inspection remains available where the host supports it; only
Loofi's distribution bundle and duplicate application-management surface were
removed. Existing compatibility data is left on disk but is not treated as a
current product contract.

## Verification

- **Automated tests:** 4,780 passed, 73 skipped, 0 failed in the deterministic
  rootless/offscreen suite.
- **Quality gates:** lint, mypy type checking, architecture, stabilization,
  product-contract, system-check, packaging-manifest, dependency-sync, and
  bytecode compilation passed locally.
- **Coverage:** 86.95% line coverage for the maintained V27 surface against an
  85% blocking gate. The planned repository-wide 90% target is deferred to the
  next release; compatibility-only modules remain exercised by the full test
  suite but are outside this maintained-surface measurement.

## Qualification boundaries

Physical desktop accessibility, authorization-agent/Polkit behavior, reboot
completion, fresh Atomic installation, and manual keyboard/Orca journeys are
recorded as **unverified** for this release under the explicit release
decision. Rootless or offscreen evidence does not imply those results.

## Upgrade notes

This is a breaking product-scope release. Scripts should use the reduced CLI
and treat `available`, `unavailable`, `stale`, and `error` as distinct states.
Install the single COPR RPM; no daemon, API package, or Flatpak bundle is
required.
