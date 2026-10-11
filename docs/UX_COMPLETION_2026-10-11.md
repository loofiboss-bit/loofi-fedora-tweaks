# Everyday UX completion and qualification — 2026-10-11

This is the follow-up to the [initial candidate report](UX_QUALIFICATION_2026-10-11.md)
for draft [PR #66](https://github.com/loofiboss-bit/loofi-fedora-tweaks/pull/66).
The earlier report remains a dated record of its own source and RPM. KDE on
traditional Fedora with DNF5 remains the first target; English remains the only
product language. No persisted product format or authorization boundary changes.

## Remaining implementation completed

- The review's long acknowledgement forced a minimum width greater than the
  available logical work area with enlarged text. A short, explicit checkbox
  retains the full accessible description. Existing scope and recovery content
  now scroll while Apply/Cancel remain visible. Cancel remains the default;
  Return in the scope does not apply, and accepting unavailable rollback still
  requires the checkbox.
- The compact guide menu explicitly accepts strong keyboard/accessibility focus.
  Its Tab traversal has a regression test.
- The performance harness now runs alternating fresh-process revision pairs,
  measures first Tweaks construction and warm navigation, and exercises
  50/200/500-row Apps fixtures. Seven widget scenarios record delivered inputs
  and observed results. Counts stop at their documented review/request boundary;
  they are not complete installation or authorization step counts.
- Every harness child has private XDG configuration, data, cache and state.
  An explicit settings fixture prevents migration of the real user's legacy
  configuration. Logs remain in the fixture. No benchmark mutates host settings.
- VM tests exercise optional guide progress across app restart, an actual
  Discover launch and return, and DNF5/Polkit installation/removal of a local
  inert package with exact payload and independent RPM readback. A separate
  before/after phase checks persistence across a real guest reboot using the
  kernel boot ID and restores the original Dolphin value.
- Fresh provisioning uses a separate empty-disk artifact. Plasma Wayland uses
  a separate base/domain and checksum-pinned upstream native input/screenshot
  helpers. The existing X11 golden image is preserved. All changes and packages
  remain inside owned guest overlays.
- Trusted CI includes reboot qualification and an optional sequential extended
  dispatch for repeat/fresh/Wayland. Both jobs require the master ref and exclude
  pull requests. Feature-branch code is never run on the trusted runner.

## Roadmap coverage and rollback

| Phase | Delivered scope | Regression evidence |
| --- | --- | --- |
| 0 | Paired process baseline, fixed catalog fixtures, scoped input counts | `test_ux_baseline.py`; isolated measurement artifact |
| 1 | Honest update states, optional first-run guidance, neutral DNF terminology | Dashboard, next-step, catalog and documentation tests |
| 2 | Remaining-only inspection, safe row merge, reused Apps rows | Snapshot budget/cancellation, filter and worker lifecycle tests |
| 3 | Next steps before meters, exact saved symptom session | History corruption/staleness, prioritization and exact navigation tests |
| 4 | One explicit review, cancel default, inline profile results | Authorization, drift, no-rollback acknowledgement and verification tests |
| 5 | Catalog-miss handoff, exact RPM identity, explicit inventory refresh | Native handoff/lifecycle, exact Flatpak identity and real Discover guest tests |
| 6 | Logical geometry, focus, scaling and accessible review state | Keyboard regressions, 24-case native/offscreen matrices, two isolated Orca runs |
| 7 | Everyday aliases, discoverable presets, dismiss/reopen/resume guidance | Catalog/guide tests and guest restart/persistence scenarios |
| 8 | Repeat overlays, empty disk, real reboot, inert package cycle, Wayland infrastructure | Host contracts and separately recorded actual guest runs below |

The original product-phase changes remain in `6f0e75d`. This follow-up adds
qualification infrastructure and the bounded review/guide focus fixes. The focused follow-up commits can be reverted independently. No saved settings, profiles, action
history, guide progress or package-data format is migrated. Guest fixtures are
removed after readback; VM rollback is limited to owned overlays. The installed
host candidate can be replaced with the prior saved RPM without deleting user
state. Larger rewrites, a new package manager and a second onboarding engine
remain unnecessary; the measured search performance does not justify debounce.

## Reproducible performance baseline

Twenty alternating fresh-process pairs compare `72175ef` with product snapshot
SHA-256 `678d18e628e0b0737e426e0741dad9d3f7695e9d5ab0f9722a64515657032bc6`.
Both snapshots exclude bytecode caches and use identical synthetic collectors,
platform, settings and inspection fixtures. Fedora 44, Python 3.14.8, PyQt/Qt
6.11.0 and the offscreen platform were used.

| Measurement | Before | Candidate |
| --- | ---: | ---: |
| Process startup/import/Qt/shell median | 406.005 ms | 409.33 ms |
| First Tweaks construction median | 72.345 ms | 75.18 ms |
| Warm navigation median | 5.24 ms | 5.06 ms |
| Full fixture process lifecycle median | 755.44 ms | 759.44 ms |
| Apps last-key-to-list p95, 50 rows | — | 7.26 ms |
| Apps last-key-to-list p95, 200 rows | — | 23.98 ms |
| Apps last-key-to-list p95, 500 rows | — | 56.70 ms |

Median paired startup change was +1.45%; individual pairs ranged from -22.40%
to +13.15%. This fixed fixture found no reproducible startup regression above
10%. All measured search sizes meet the 150 ms p95 target. Construction samples
were 87.34/230.70/463.26 ms respectively and are single observations.

These numbers exclude system collection, disk-cache-cold starts, Polkit and
physical desktop latency. They do not justify debounce or a model/view rewrite.
Reproduce with:

```bash
python3 scripts/measure_ux_baseline.py --compare-ref 72175ef \
  --startup-pairs 20 --samples 30 --catalog-sizes 50,200,500 > baseline.json
```

The local detailed artifact is `/tmp/loofi-ux-baseline-2026-10-11-final.json`.
Record `--rpm PATH` when tying a new measurement to a built package.

## Accessibility qualification

The real review dialog passed 24 cases on the host's native Wayland platform:
light/dark/high-contrast, 100/125/150/200% Qt scaling, and 12/18-point text.
The same offscreen matrix passed. Checks cover bounded logical geometry,
visible primary buttons, accessible names/descriptions, Tab leaving the scope,
explicit Space acknowledgement and Escape cancellation. These are targeted Qt
widget events, not a claim that every app workflow was driven by global keys.

```bash
python3 scripts/check_gui_accessibility.py --platform wayland \
  --output-dir test-results/accessibility-wayland
```

Screenshots and per-case facts are local artifacts. Two isolated installed-Orca runs passed on native Wayland. Actual generated
speech identified the exact scope, acknowledgement name, unchecked status before
Space, checked status after Space, and Apply/verify button. The audio server was
disabled; human listening/comprehension remains separate. Ten regression tests
cover negation-safe parsing, step boundaries, stale artifacts and process cleanup.
Nine additional Qt keyboard regressions cover Apps, optional introduction,
Tweaks/profile navigation and review controls. They make no global KWin-input claim.

## Execution evidence

The proportionate automated qualification is complete. `LOOFI_IPC_MODE=disabled QT_QPA_PLATFORM=offscreen
just verify` passed 5,341 tests, 2,146 subtests, 33 skips and 85.53% coverage
(22 warnings). Packaging, catalog, translation inventory and wiki mirror checks
passed. The final full run includes keyboard, Orca and process-ownership regressions. Completed guest runs and exact RPM hashes are recorded below; remote checks apply to the pushed head.
The first expanded X11 run passed the controlled package cycle and existing
security flows but exposed test-navigation failures. Those failures were fixed
by clearing/scoping global search and matching Qt's disclosure role; they are
not presented as a passing whole-suite run.

## Guest qualification results

The first full final-payload X11 overlay run passed 10 before-reboot tests and
one after-reboot test. One test is intentionally skipped in each phase because
it belongs to the other side of the actual reboot. Both kernel boot IDs were
recorded and differ. Reports: `test-results/e2e-repeat-16/`.
RPM SHA-256: `7cdee7f58c340ad74da8ae9917d1fa61d8fd0bb77daa2662b28ec4f468d665e5`.
Earlier exploratory runs exposed automation navigation/process-ownership issues;
they are retained as failure evidence and do not count as successful qualification.
A second consecutive clean-overlay run also passed 10 before-reboot tests and
one after-reboot test (`test-results/e2e-repeat-17/`). Its RPM SHA-256 is
`3f2299e8ff96694187525c62fd3ed44fd3ec21c7efc2a65d6ccdfe4af8cd5ff9`,
matching the installed host candidate below. The additional empty-disk run was started but stopped before qualification,
following the user's request to avoid disproportionate testing. Its partial
owned guest is removed without changing the reusable X11 base. Plasma Wayland
VM provisioning was not run. Fresh provisioning and Wayland support are covered
by host contracts, but those actual guest environments remain unqualified.

## Installed host candidate

The local candidate was reinstalled through Polkit and DNF5, cache-only with
all repositories disabled. Exactly one Loofi package was replaced. RPM SHA-256:
`3f2299e8ff96694187525c62fd3ed44fd3ec21c7efc2a65d6ccdfe4af8cd5ff9`.
Installed identity: `1:32.8.0-1.fc44.noarch`. `rpm -V`, offline `dnf5 check`,
installed CLI/package smoke and an isolated offscreen GUI startup passed.
All 19 hashed user-state files remained unchanged. The private backup/readback
is under `/tmp/loofi-ux-host-install`; no user data is included in the repository.
The already-running desktop app was left open and needs restarting to load the
new code. This is a local unsigned candidate, not a published release.

## Evidence boundaries

Physical hardware, human screen-reader use and user comprehension require their
own results. GNOME/Atomic compatibility continues to have automated regression
coverage; the new KDE/Discover guest scenarios do not qualify those desktops.
No publication, merge or release is implied by this report or draft PR.
