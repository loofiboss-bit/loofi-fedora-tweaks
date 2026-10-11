# Guide candidate verification

Local candidate for 32.8.0 "Guide", checked on 2026-10-11. This report covers
the four everyday guides, their local progress store, navigation and search,
and the installed RPM. Hardware diagnostics and app-source insight remain
roadmap work.

## Product and data boundaries

The Overview offers optional workflows for making Fedora yours, choosing and
managing apps, maintaining the system, and solving a problem. The compact
guide indicator remains available while navigating. Selecting a step routes
to the relevant existing page or review surface; it does not start an
operation. Users can review or skip a step, leave the guide, and resume it
later. Only a referenced successful operation can mark an operation result as
verified; missing or stale evidence stays explicit.

Guide definitions and progress models are Qt-free. Progress uses a separate,
versioned XDG state file with private atomic writes, lock/revision checks, and
fail-closed handling for corrupt or future formats. Existing profile and
operation-history formats are unchanged. `guides list` and `guides show <id>`
are read-only CLI views; the CLI cannot execute a guide chain.

## Verification results

- `just verify`: passed: lint, type checking, architecture and product/version
  contracts, and the complete suite: 5,129 passed, 33 skipped, 2,065 subtests,
  22 warnings, and 85.54% coverage.
- `just check-packaging`: passed; source/wheel manifest and requirement
  synchronization validated.
- Fedora 44 installed-RPM check: built and installed 32.8.0 in an isolated
  rootless Podman container, then ran the installed version/help commands and
  `scripts/package_smoke.py` as a regular user with isolated XDG paths and no
  checkout import path. All passed. The headless container correctly exposes
  no desktop-specific built-in profile; the smoke check accepts that empty
  filtered view and separately requires the static preset catalog.
- Rendering: 24 captures at scale 1 and 24 at scale 2, covering 900×650 and
  1280×800, light and dark presentation, and six application surfaces. The
  clipping counter was zero at each scale. This is automated offscreen
  rendering, not physical KDE qualification.
- GitHub Actions was not run remotely. The PR workflow now contains the same
  installed-RPM check; the local Fedora 44 container completed it.

## Startup and navigation measurement

To compare the local candidate with the parent revision, the parent source was
exported from commit `fbbb938648083db3ab9b2b3b01aa52a3773cafbf`. Both versions
ran on the same host, Python 3.14.8 and PyQt 6.11.0 environment with
`QT_QPA_PLATFORM=offscreen` and fresh private XDG directories. Twenty paired,
alternating process runs created `QApplication` and `MainWindow`, processed
initial events, then navigated from Overview to Tweaks and performed eight
warmed Overview/Tweaks round trips. The shell-start metric spans imports through
the first event pump. Values are medians; paired delta is the median of each
after-minus-before pair. Route-hop time is one round-trip divided by two.

| Measurement | Parent median | 32.8 median | Paired median change |
|---|---:|---:|---:|
| Import, Qt application, shell construction, first event pump | 288.3 ms | 298.3 ms | +2.1 ms |
| First navigation to Tweaks | 37.1 ms | 36.0 ms | −0.7 ms |
| Warm Overview/Tweaks route hop | 0.321 ms | 0.375 ms | +0.027 ms |

The paired route-hop change is under three hundredths of a millisecond. Startup
timings varied by hundreds of milliseconds between paired runs, while first
navigation and route-hop differences were also smaller than within-version
spread. The measurements show no reproducible user-visible regression to
optimize. They do not measure compositor latency, physical hardware, or
user-perceived interaction on KDE.

## Remaining physical qualification

The following remain untested on a real KDE session: changing and restoring a
setting through the guide, denied or cancelled Polkit, opening and returning
from external KDE settings, physical keyboard-only use, and screen-reader
behavior. No claim about those paths is implied by the automated tests or
rendering captures.
