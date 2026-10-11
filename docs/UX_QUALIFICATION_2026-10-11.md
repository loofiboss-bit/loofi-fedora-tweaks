# Everyday UX implementation qualification — 2026-10-11

This report records the local implementation candidate for the everyday UX
roadmap. The working tree is based on `72175ef9498a1650eee0806e16cf9ddc915543e8`
on `codex/everyday-diagnostics-32-8` and is uncommitted. The Fedora 44 RPM
candidate is `loofi-fedora-tweaks-32.8.0-1.fc44.noarch.rpm`, SHA-256
`589597f304fbdb2a58906fb9e132ac833b2e1ad01a838e9060875386725b2aca`.

## Implemented

- Overview distinguishes unchecked, unavailable, failed, stale, and verified
  update results. It places up to three evidence-based next steps and recorded
  maintenance before resource measurements. A saved symptom diagnosis links to
  its exact Health session and remains distinct from System Check.
- The first-run introduction remains optional, stays available after routine
  checks, and can be reopened after dismissal. Navigation and guidance do not
  start a system operation.
- Tweaks can continue checks skipped by the shared inspection budget without
  re-reading completed rows. Full Refresh still performs a new full check.
  Loofi's curated default is labelled separately from the desktop's actual
  default, everyday search terms reach existing controls, and DNF choices no
  longer promise speed.
- System-setting changes, restorations, and reviewed Health actions present
  exact values, scope, and recovery guidance in one cancel-default dialog.
  Missing automatic rollback requires explicit acknowledgement. Profile results
  remain inline with an exact Activity link; OperationController confirmation,
  fresh preflight, drift detection, Polkit, and readback remain in force.
- Apps offers a clearly scoped Discover/GNOME Software handoff when the
  curated catalog has no match. RPM removal names and can copy the exact package
  identifier, explains the external handoff, and directs users to refresh on
  return. Catalog row widgets are reused across filters.
- Logical work-area sizing, dialog keyboard behavior, active translation-source
  checks, guides, catalogs, and user documentation received focused updates.
  English remains the only product language.

## Validation

- `LOOFI_IPC_MODE=disabled QT_QPA_PLATFORM=offscreen just verify` passed 5,282
  tests, 2,118 subtests, 33 skipped, and 85.46% coverage; lint, type checking,
  architecture checks, and catalog checks passed. The run reported 22 warnings.
- The system-review, restore, Apps handoff, and dialog regressions passed
  62 focused tests. A separate keyboard regression passed, confirming that Tab
  leaves the read-only scope, Escape cancels, and Return does not apply.
- `just check-packaging` passed. Generated tweak documentation, the English
  translation-source inventory, wiki mirror, and `git diff --check` passed.
- `just test-full` built and installed the RPM in the existing isolated Fedora
  44 KDE Plasma X11 guest. All six AT-SPI tests passed in 277.40 seconds with
  one upstream GLib deprecation warning. The suite denied and authorized
  Polkit requests, read back the DNF value, restarted Loofi, restored the saved
  value, and verified the real DNF configuration. The owned guest overlay was
  discarded. See `test-results/e2e/summary.json` and the local
  `test-results/e2e/pytest.log` for the build and run evidence.
- With a fixed synthetic 500-row Apps catalog, Python 3.14.8, PyQt 6.11.0,
  Qt 6.11.0, and the offscreen platform, last-key-to-filtered-list p95 measured
  171.89 ms before row reuse and 13.81 ms after it (about 92% lower). Catalog
  widget construction measured 481.69 ms and 495.14 ms respectively; each is a
  single sample, so these figures do not qualify process startup or establish a
  statistically reliable construction-time change.

## Remaining qualification gaps

- The performance harness currently measures Apps catalog construction and
  search only. Paired process-start measurements, first page open, navigation,
  other catalog sizes, and end-to-end step counts still need a repeatable
  baseline.
- The VM run reused the existing golden guest and exercised a disposable
  overlay. It did not provision from an empty disk or reboot the guest to verify
  persistence. Only one final candidate VM run is recorded here.
- The guest uses Plasma X11. Plasma Wayland, physical KDE scaling and themes,
  GNOME, actual screen-reader use, and hardware remain unqualified. Automated
  Qt focus tests and offscreen geometry checks do not substitute for these.
- Guide progress has store/widget coverage, but restart/resume is not in the
  final AT-SPI suite; the guest's combo-box selection was not reliable enough to
  support that test. Discover/GNOME Software and package-removal handoffs were
  tested through their controlled UI and unit seams, not by driving an external
  software manager in the guest.
- Remote GitHub CI was not run. The translated-source check validates remaining
  inventory references; it does not extract the whole interface or make the
  English-only product localization-ready.
