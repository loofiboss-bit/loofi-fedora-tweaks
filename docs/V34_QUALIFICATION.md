# v34.0.1 Accord qualification

Status: implementation, source checks, packaging, and native Flatpak integration
are complete. Full automated qualification is BLOCKED by a reproduced Qt
accessibility crash. No commit, pull request, publication, or installation on
the host is implied by this report.

## Required automated checks

- Focused backend, policy, CLI, and Qt regressions: passed. New regression cases
  include reviewed-evidence rendering, true signal cancellation, runtime reuse
  across installations, source/location drift, and global ref filtering.
- `LOOFI_IPC_MODE=disabled QT_QPA_PLATFORM=offscreen just verify`: passed,
  5,436 tests, 2,168 subtests, 33 skipped, 85.43% coverage. The 22 warnings were
  retained in the test output. Includes lint, mypy, architecture, catalog,
  translation-location, and version checks.
- `just check-packaging`: passed, including wheel/sdist manifest builds.
- RPM build: passed through the canonical VM runner,
  `loofi-fedora-tweaks-34.0.1-1.fc44.noarch.rpm`, SHA256
  `5c3c40c882bc6e6bb89dd6c20628aa0ca02d770ee5e380eb612bc80460d5ec4d`.
- Disposable Fedora 44 KDE/X11 `just test-full`: FAILED, 6 passed and 1 failed
  before stop-on-first-failure, in 370.97 seconds. Failure and diagnostics are
  described below; this is not a qualified candidate.
- Signed local Flatpak fixture: both integration tests passed for the exact RPM.
  User, system, and named installations verified their selected app and runtime
  commits independently; unrelated apps, other installations, and app data were
  preserved. CLI discovery, stale-review rejection, and shared-runtime reuse
  without a user duplicate passed.
- Theme/scaling/layout: passed, 216 isolated offscreen captures across light,
  dark, high contrast, 900x650/1280x800/1600x900, 100%/150%/200% scaling, and
  normal/enlarged text. Candidate lists, partial discovery, per-ref results,
  and review dialogs had no detected wrapped-label clipping or horizontal
  overflow; keyboard focus was present and review defaults to Cancel.
- Keyboard selection/filter retention, inert scoped navigation, obsolete worker
  results, cancellation, and page shutdown: focused Qt regressions passed.
- Independent read-only security/correctness review: completed; identified
  dependency-source, cancellation-propagation, and global-filter findings were
  corrected and rechecked. Native system-helper commit handling was reviewed;
  unsigned local system sources are rejected, and source trust parsing uses
  GLib.KeyFile with exact keys and UTF-8 byte lengths. Six real-GLib cases
  and helper regressions passed with no remaining concrete P1/P2 findings in
  the reviewed Flatpak guard. The separate Qt blocker remains open below.
- `git diff --check`, version consistency, and existing wiki mirror check: passed.

## Reproduce rendering checks

Run each scale in a fresh process, with and without `--large-text`:

```bash
python3 scripts/capture_flatpak_updates_screenshots.py /tmp/loofi-v34-render --scale 1
python3 scripts/capture_flatpak_updates_screenshots.py /tmp/loofi-v34-render-large --scale 2 --large-text
```

Each invocation captures 36 cases and writes `rendering-checks.json`. The
complete matrix uses scales `1`, `1.5`, and `2` for both text sizes. Fixture
processes use isolated XDG paths and prohibit host subprocess observations.

## Early VM baseline

The clean-overlay early baseline completed with 9 passed and 2 intentional
reboot-only skips in 847.43 seconds. The installed baseline RPM was
`loofi-fedora-tweaks-33.0.1-1.fc44.noarch.rpm`, SHA256
`d7cf4a987a8c52848238d7a65d3600165e895670f9101f4196895eae6e0b207b`.
Reports are under `test-results/e2e-v34-baseline/`. The owned guest stopped and
its disposable overlay was discarded. The earlier Qt crash was not reproduced
in that run; this baseline does not qualify the v34 implementation.

## Blocking Qt accessibility failure

The exact candidate failed
`test_navigation_user_setting_verification_and_restore` when switching from
Activity to Tweaks. The application process received SIGSEGV in Qt 6.10.2:

```text
QAccessibleCache::idForObject
QAccessible::queryAccessibleInterface
QAccessibleAbstractScrollArea::child
AtSpiAdaptor::accessibleInterface
```

The guest kernel independently recorded a general protection fault in
`libQt6Gui.so.6.10.2`. Filtered core frames, JUnit, exact package identity,
and passed Flatpak evidence are preserved in
`test-results/e2e-v34-signed-qt-failed/`. The guest stopped and its disposable
overlay was discarded. No v33 waiver applies.

Upstream [Qt scroll-area accessibility source](https://github.com/qt/qtbase/blob/v6.10.2/src/widgets/accessible/complexwidgets.cpp#L471-L474)
indexes `accessibleChildren()` without bounds checking. That list excludes
hidden scrollbar containers. The [AT-SPI adaptor](https://github.com/qt/qtbase/blob/v6.10.2/src/gui/accessible/linux/atspiadaptor.cpp#L1539-L1548)
checks only negative indices before calling `child(index)`. An index read
before a page hides can therefore exceed the new child count. Loofi's route
keeps the scroll area and viewport alive and performs ordinary stacked-page
navigation; no viewport replacement or scroll-child deletion was found.

A standalone C++ reproduction using only QApplication, QScrollArea, and
QAccessible also failed with SIGSEGV on the host's Qt 6.11.2, with offscreen
rendering and isolated XDG state. It printed:

```text
Qt 6.11.2 visible children=3
Hidden children=1; requesting previous index=2
```

The child process exited `-11`. Core generation was disabled. Source and JSON
result are in `test-results/qt-scroll-accessibility-repro/`; it did not operate
the host desktop or install packages. This establishes an independent Qt
failure, rather than inferring one from a missing UI node.

A correct dependency fix must validate the index against the same local child
list before lookup. PyQt6 does not expose the accessible-interface factory
needed for a narrow Python override. Replacing ordinary page hiding, disabling
accessibility, skipping the test, or repeating runs until green would not
resolve this defect. Qualification remains blocked pending a corrected Qt
runtime and a successful full candidate run. No remote issue was filed.

## Candidate diagnostic run

A v34.0.1 clean-overlay diagnostic run passed 11 tests with 2 intentional
reboot-only skips in 916.75 seconds. It exercised real user, system, and named
Flatpak updates, dependency readback, unrelated application preservation, app
data preservation, stale-review rejection, Activity/Tweaks navigation, Polkit
denial and authorization, restoration, and native search. Kernel crash entries
and coredump frames were empty. Reports are preserved under
`test-results/e2e-v34-diagnostics-passed/`.

Its RPM SHA256 was
`1e84025e2c2572bfc82638009d4094f48f8fd0ea1ac1b0f8bc940760559080d2`.
This run predates the final local-system-source guard and signed fixture, so it
is diagnostic evidence, not the final candidate qualification. An earlier
candidate attempt passed both Flatpak integrations but failed when the app
vanished during Activity/Tweaks navigation; no crash diagnosis was available
in that attempt. The subsequent diagnostic run passed that navigation without
a Qt crash. No v33 exception was applied.

## Baseline and version identity

The starting checkout was clean at `9c388c4`, the Concord documentation follow-up.
The remote master readback was its PR #71 merge, `afab2e4`. The latest published
release was v33.0.1. Historical `v34.0.0` names Citadel at `59e1963`; it is not
rewritten. The new local candidate is v34.0.1 Accord.

The v33.0.1 guest Qt6Gui crash remains historical failed evidence until a current
candidate run establishes its own outcome. The version-specific v33 release
exception is not applicable to this candidate.

## Limits

Only automated checks are acceptance requirements. Physical KDE/GNOME,
hardware, and human screen-reader behavior are not inferred from mocks,
offscreen rendering, or VM tests. GitHub CI and publication require separate
authorization and independent readback.
