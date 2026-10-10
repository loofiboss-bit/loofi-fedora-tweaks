# Routine 32.7.0 local qualification

Checked on 2026-10-10. This is a locally qualified candidate based on Personal,
not a published or installed release.

## Implemented workflow contracts

- Apps compares one captured inventory using exact Flatpak IDs and six explicit
  RPM counterparts. Installation, architecture and branch identities stay separate.
  Detail/removal requests preserve the exact selected installation and ref.
- Health's storage guide records root, home and var use, grouping shared devices
  without summing them. Incomplete cache reads remain unknown; journal bytes are
  measured data, not promised recoverable space. Existing reviewed owners perform
  DNF/Flatpak cleanup. Check again is a deliberate new symptom inspection.
- Updates and upgrade preparation share strict bounded cache-only DNF5 restart
  parsing. The GUI checks only on request, retains the result in session memory,
  and marks it stale after the existing 24-hour freshness interval.
- Overview carries typed source/run/symptom context. Links select the right
  destination without starting checks; exact recorded-operation links retain
  Activity's missing-record behavior.
- Profile comparisons read saved same-desktop targets only. Unknown IDs/values
  remain exact. Edit-copy and fresh-review actions use existing profile flows.

Portable profile and action-history schemas, user configuration and mutation
authority are unchanged. No dependency, background service or main route was added.

## Automated and packaging evidence

The final full gate passed:

```bash
LOOFI_IPC_MODE=disabled QT_QPA_PLATFORM=offscreen just verify
just check-packaging
just build-rpm
git diff --check
```

- 5,089 tests passed, 33 skipped, 2,058 subtests passed.
- Coverage: 85.63%, exceeding the maintained 85% gate.
- Lint, type checks, stabilization, architecture, product catalog, synchronized
  version sources and package manifest checks passed.
- RPM and SRPM for 32.7.0 built under
  `/tmp/loofi-fedora-tweaks-build/rpmbuild/`; neither was installed.
- Independent read-only review found no remaining concrete correctness or
  regression issues; its 117 focused tests passed.

Logs: `/tmp/fedora-routine-verify-final.log`,
`/tmp/fedora-routine-packaging.log`, `/tmp/fedora-routine-rpm.log`.

## Rendering evidence

```bash
PYTHONPATH=loofi-fedora-tweaks python scripts/capture_routine_screenshots.py /tmp/fedora-routine-ui --scale 1
PYTHONPATH=loofi-fedora-tweaks python scripts/capture_routine_screenshots.py /tmp/fedora-routine-ui --scale 2
```

The isolated matrix produced 40 images: five reachable feature presentations,
light/dark themes, 900x650 and 1280x800 logical viewports, at 100% and 200% scale.
The script rejects unexpected host subprocesses and records visible Tab-focus
targets and wrapped-label geometry. Both scale reports recorded zero views with
clipped wrapped labels after correcting the storage observation label height.
Application comparisons, profile differences, Updates, contextual Overview and
Health storage were visually inspected. Scrolling exposes content below the
viewport; comparison tables retain their normal horizontal scrolling for long refs.

Captures, contact sheet and JSON reports are under `/tmp/fedora-routine-ui/`.
Fixture screenshots and focus-target inventory do not qualify actual keyboard,
screen-reader or external-window interaction.

## Read-only runtime observations

The actual CLI commands were run with isolated temporary XDG directories:

```bash
loofi-fedora-tweaks --cli --json apps compare org.mozilla.firefox
loofi-fedora-tweaks --cli --json updates restart-advice
loofi-fedora-tweaks --cli --json tweaks profile library compare focus privacy-basics
```

App comparison returned valid JSON, one installation and no unknown sources.
Built-in profile comparison returned valid JSON with five entries. Restart advice
returned valid JSON with an unknown state and exit 1: the cache-only DNF command
reported missing cache for repository `fedora`, producing no reboot JSON. This is
an unavailable observation, not a no-restart recommendation. No metadata refresh,
package operation or restart was attempted.

## Remaining physical qualification

Physical KDE interaction, native software-manager handoff, real reviewed cleanup,
200% desktop scaling, keyboard traversal and assistive technology remain unverified.
GNOME and Atomic have automated restrictions/shared-flow evidence only; no physical
qualification or Atomic support expansion is implied.

Qualification did not perform commits, pushes, pull requests, releases, installation,
desktop settings changes, service changes or publication. Any later PR is separate
from these local qualification results.
