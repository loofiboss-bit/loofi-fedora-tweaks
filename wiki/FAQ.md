# FAQ — v27.0.1 "Core"

## What is Loofi Fedora Tweaks?

Loofi is a focused Fedora maintenance core: read-only inspection, clear
capability states, native desktop handoffs, and reviewed system changes. The
GUI has five primary destinations and the CLI has eight bounded top-level
commands.

## Which Fedora systems are supported?

Fedora 43 and 44 are the stable targets; Fedora 45 is preview-only. The
application detects desktop/session and deployment capabilities instead of
assuming KDE or a traditional DNF host. GNOME, KDE, XFCE, Sway, Atomic, and
bootc paths can report supported, unavailable, or manual-only states according
to the detected capabilities.

## Does it work on Silverblue or Kinoite?

The capability-aware Atomic path recognizes `rpm_ostree` and bootc and keeps
their update/reboot semantics separate. Fresh Atomic installation and physical
reboot completion were not manually qualified for v27.0.1, so those gates are
unverified rather than claimed as passed.

## Do I need administrator access?

No for inspection. A reviewed persistent change may request authentication from
the desktop's standard Polkit agent through `pkexec`. Loofi never runs the
whole application as root and never stores passwords.

## Can I use the CLI?

Yes. Use `loofi-fedora-tweaks --cli --help`; place `--json` before the command:

```bash
loofi-fedora-tweaks --cli --json info
loofi-fedora-tweaks --cli changes list
```

## Does Loofi install applications?

Application discovery is handed to the native software center through an
AppStream/XDG link. Loofi no longer mirrors a marketplace or owns install and
remove controls.

## Does it run in the background?

No. v27.0.1 has no background daemon, local Web API, unattended scheduler,
automatic reboot, retry, or rollback. Host mutations are explicit Action
Center plans and require independent verification.

## How do I report a problem?

Run `loofi-fedora-tweaks --cli doctor` and
`loofi-fedora-tweaks --cli support-bundle`, review the redacted output, and
include the Fedora variant, backend, exact route/command, and reproduction
steps in an issue.
