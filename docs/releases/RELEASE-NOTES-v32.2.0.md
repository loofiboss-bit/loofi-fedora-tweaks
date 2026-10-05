# Loofi Fedora Tweaks 32.2.0 — Coherence

Coherence improves confidence in the everyday Tweaks and Apps flows while
keeping the existing four primary destinations and visual identity.

## Highlights

- Tweaks checks share a 20-second time budget, reuse KDE schemas within a
  snapshot, report progress, and support cancellation. Completed readings stay
  visible; unchecked values remain explicitly unknown.
- Recovery language distinguishes restoring a verified previous value from
  applying Loofi's curated standard value. Catalog values are not described as
  the installed desktop's own defaults, and recovery guidance reflects each
  action's actual support.
- Apps shows Flathub availability and installation scope before review. Missing
  sources link to the existing manual guidance; unknown status explains the
  failure and can be checked again. Selected apps are retained when returning
  from setup guidance, and install preflight checks requirements again.
- Generated tweak documentation and active version-source alignment are part
  of the maintained local verification and CI gates.

## Qualification

The 4,617-test suite, package checks, and local RPM build passed before
publication. A KDE Dolphin value was changed, independently read back, and
restored on the development host. GNOME behavior, visible effects, full KDE
coverage, keyboard and screen-reader use, scaling, and Atomic workflows remain
unverified. Automated tests do not qualify those environments.

## Install

Download the RPM asset below and install it on Fedora with:

```bash
pkexec dnf install ./loofi-fedora-tweaks-32.2.0-*.rpm
```

Existing application settings and history remain in the user's home directory.
