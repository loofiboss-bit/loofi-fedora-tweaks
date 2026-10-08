# Companion qualification

Local candidate: v32.5.0 "Companion", 2026-10-08.
This document distinguishes automated checks, local read-only runtime evidence,
and physical interaction. The candidate is not installed or published by this work.

## Automated checks

The final integrated checks passed on the Fedora 44 development host:

| Check | Result |
| --- | --- |
| `LOOFI_IPC_MODE=disabled QT_QPA_PLATFORM=offscreen just verify` | Passed: lint, mypy, architecture, product catalog/version, 4,988 tests, 1,997 subtests; 33 skipped; coverage 85.35% |
| `just check-packaging` | Passed: synchronized dependencies and built wheel/sdist manifest |
| `just build-rpm` | Passed: `1:32.5.0-1.fc44.noarch`; new Companion modules confirmed in RPM payload |
| `git diff --check` | Passed |
| Independent focused review | Passed; notifier-tool dependency and late native-launch race corrected; no remaining concrete findings |

Focused and integrated tests cover malformed/cross-desktop profiles, drift,
cancellation and restoration, exact Flatpak identities and override scopes,
masking, partial evidence, saved-session comparison, ScreenCast failures,
support export without collection, reboot uncertainty, and simultaneous reader
shutdown. A reproduced Qt teardown lock was fixed by returning completed
workers to the GUI thread before deletion; success/failure affinity and repeated
worker-lifecycle regression tests pass.

The isolated rendering matrix covers 450 views across three themes and three
window sizes, at 100% scale and 200% scale with large text. Its 9,000 automated
focus traversals report no clipped wrapped labels, clipped control text, table
theme issues, or outer horizontal overflow. Health, Tweaks, and Updates captures
were visually inspected. This matrix does not qualify external settings tools.

## Local read-only runtime evidence

- Before the appearance extension, source Tweaks, Health, and Updates components were exposed on the actual
  KDE/Wayland compositor with isolated application state. Captures were inspected.
  Programmatic focus traversal was exercised; physical keyboard use remains
  unverified, and the standalone Updates component did not provide named focus
  readback in that smoke test.
- Installed Flatseal's full `app/com.github.tchx84.Flatseal/x86_64/stable` ref in
  the system installation produced an available access report with all five
  declaration/system/user override layers. This is metadata evidence only.
- Native handoff discovery found both Flatseal and KDE's actual
  `kcm_app-permissions` module. External permission windows were not launched.
- Upgrade preparation observed repository state and free space. A timed-out
  package-health probe and unavailable usable reboot JSON remained unknown,
  producing a partial report rather than an all-clear.

## Physical qualification

KDE is the primary target. Actual source-window exposure is confirmed above;
rendering and keyboard checks are automated. Native computer-control APIs are
unavailable in this task, so human interaction and external-window qualification
remain separate. Automated/offscreen tests do not prove these interactions.

- KDE profile change and restoration: unverified.
- New pointer theme/size and Plasma style changes, restoration, and visible effects: unverified.
- Real X11 native Cursor Settings launch: unverified.
- Physical keyboard, scaling, and permission-tool handoff workflows: unverified.
- Real screen sharing in a target application: unverified.
- Assistive technology: unverified.
- GNOME physical workflows: unverified; optional controls only.
- Atomic physical workflows: unverified; no expanded support promise.

## Boundaries

- Profiles retain existing Action Center review, drift checks, and independent verification.
- Access reports contain declarations and override layers, not effective runtime guarantees.
- Partial or incompatible Health evidence cannot resolve a finding.
- Screen-sharing checks do not capture media or restart services.
- Support export reads one saved session and masks edited text again; review before sharing.
- Upgrade preparation does not download packages, execute a major upgrade, or reboot.
- Backup checklist choices are manual confirmations, not backup verification.
- These qualification checks perform no installation, merge, or publication.
  Git commits and a draft pull request are handled separately from qualification.

## KDE appearance extension — 2026-10-08

The catalog now contains 79 controls. Added pointer theme, requested pointer
size, and Plasma style share GUI search/favorites, portable profiles, CLI and
Action Center restoration. The final full verification above includes 48 new
regression tests. Profile tests use the real controller and temporary run/plan
stores, exercising both pointer-setting orders, exact custom-size restoration,
removed prior themes, later independent changes, notification failures and CLI
JSON evidence. Native owner tests cover asynchronous discovery/revalidation and
shutdown before or during a launch probe.

The two renewed full rendering matrices cover 450 views and 9,000 focus
traversals at 100% scale and at 200% scale with large text, across three themes
and three sizes. No wrapped-label/control-text clipping, table theme issue or
outer horizontal overflow was reported. Twelve additional focused pointer/X11
views exercised long names, native handoff controls and 360 focus traversals;
wrapped labels fit and horizontal overflow was absent. Pointer, X11 handoff
and separate Plasma-style captures were visually inspected. The complete long
selected pointer name remains readable in its saved-value label even when the
closed dropdown cannot display its entire text. These are fixture/offscreen
checks, not physical keyboard, external-window or assistive-technology proof.

Read-only source runtime inspection on the actual KDE Wayland host found all
three new controls ready: four installed pointer themes, current requested
pointer size 32, and eight installed Plasma styles. No setting change or pointer
signal was performed. A read-only missing-key check confirmed empty successful
`kreadconfig6` output, allowing the validated installed cursor schema defaults.
The RPM payload contains the new native owner module and updated domain modules;
all 15 changed production Python files match their source bytes exactly.

Saved configuration and notification delivery are separate results. Missing
`dbus-send` does not disable saved readback or restoration; failed notification
stops the profile but leaves successful saved runs eligible for restoration.
Pointer theme and size remain separate history resources. Prior dynamic themes
are restorable only while KDE's validated theme list includes their identifier;
an installed alias omitted by that list requires manual native recovery.
Pointer mutation is limited to KDE Wayland. X11 uses a checked native handoff.
Plasma style changes do not apply a global theme or install theme packages.
Portable profile and action-history formats are unchanged. Physical effects
and real changes/restoration remain explicitly unverified.
