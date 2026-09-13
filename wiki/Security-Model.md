# Security Model — v27.0.1 "Core"

Loofi Fedora Tweaks uses **Changes** (the Action Center) as the only authority
for persistent host mutations. GUI and CLI inspection paths are advisory and
cannot run arbitrary commands.

## Action lifecycle

Every supported change follows:

`request → closed plan → fresh preflight → explicit confirmation → bounded
execute → independent verify → typed outcome`.

Plans contain an allowlisted action definition and typed parameters. Unknown,
unsupported, high-risk, unverifiable, or missing-recovery requests remain
review-only or unavailable.

## Command boundary

- Native authorization uses the desktop's `pkexec`/Polkit agent when required.
- Subprocesses use explicit argument vectors, bounded timeouts, and no shell
  interpreter or `sudo`.
- UI modules do not import mutating services or call subprocesses.
- CLI input rejects arbitrary command vectors, shell fragments, unattended
  schedules, implicit confirmation, and remote targets.
- No automatic reboot, retry, rollback, or background scheduler exists.

## Platform and state safety

The immutable `PlatformProfile` drives eligibility for navigation, updates,
handoffs, and Actions. Unknown desktop, session, deployment backend, or reboot
state fails closed. Traditional DNF5 and Atomic/bootc paths never share a
command assumption.

Action plans and runs are persisted atomically with schema checks, bounded
leases, redacted support export, and future-schema read-only behavior. The
application never requires or stores user passwords, tokens, or private keys.

## Removed trust surfaces

The v27.0.1 product does not ship a background daemon, local Web API, external
plugin execution, specialist marketplace, or Flatpak application sandbox.
Host Flatpak inspection is optional and read-only unless a reviewed Action
Center definition explicitly supports a change.

Physical Polkit-agent behavior and manual accessibility qualification are
separate gates and remain **unverified** for this release.
