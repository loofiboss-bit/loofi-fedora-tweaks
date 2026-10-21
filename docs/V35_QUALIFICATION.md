# v35.0.0 Everyday qualification

This records local verification for the v35.0.0 release source. Passing source
checks does not establish desktop qualification. Public release assets and
canonical workflow results are recorded separately from local artifact hashes.

The maintainer revised the release policy on October 21, 2026: use relevant
regressions, routine quality checks and a working package build. Large VM
matrices and complete desktop qualification are complementary evidence,
rather than mandatory release gates. This changes the release threshold,
not the meaning of a passed test or a known defect.

## Scope

Local AppStream discovery, explicit metadata download, exact RPM/Flatpak
application transaction review, RPM removal, optional reviewed source/codec
setup, and consistent interruption recovery. Traditional Fedora KDE with DNF5
is the primary target. Existing profile, guide, route and history contracts are
retained. Major Fedora upgrades remain preparation and guidance.

## Automated gates

- Full `LOOFI_IPC_MODE=disabled QT_QPA_PLATFORM=offscreen just verify`: passed,
  5,674 tests, 33 skipped, 2,426 subtests, 85.38% maintained coverage on October 21.
- Packaging manifest/wheel/sdist: passed; both privileged helpers are included.
- RPM build: passed. The final local candidate is retained under
  `test-results/v35/local-final-rpm/` with a source-file/hash manifest; SHA256
  `36b8caaa899b1cedd5dc97811463400bd719db57aa617f84788771ffb5b8c311`.
  That artifact is not yet natively qualified. Each VM run records its own RPM
  identity; a later source build cannot substitute for the tested bytes.
- Search: p95 52.70 ms in the 500-row fixture (30 samples).
- Startup: paired median +3.81% against `f561408` (10 pairs).
- Rendering: 252 captures at scale 2 with large text, no detected text clipping,
  horizontal scrolling or table theme issues. This is offscreen layout evidence.
- Native Qt regression: installed Qt 6.11.2 fails, child exit `-11`;
  the isolated corrected QtWidgets build passes, child exit `0`.
- Exact final RPM Fedora KDE X11/Wayland and reboot qualification: not completed;
  complementary under the revised release policy.

The full suite exposed a pre-existing Gist test isolation defect: session tokens
survived between tests. That module now isolates session secrets and disables
desktop keyring access. The missing-token test asserts that no request is sent.

## Qt runtime qualification boundary

`python3 scripts/qualify_qt_scroll_accessibility.py` builds and executes an
isolated native probe. The installed runtime still accepts a stale accessibility
child index after hiding a scroll area and segfaults. Accessibility stays enabled.

`packaging/qt/qtbase-scroll-area-accessibility.patch` bounds-checks against the
same captured child list. Its application was dry-run checked against upstream
Qt 6.10.2 and 6.11.2 sources. `scripts/build_qualified_qt_widgets.py` now builds
the complete QtWidgets library from a hash-verified official 6.11.2 source
archive against matching Fedora Core/Gui. All 72 Widgets features match.
The native regression and a PyQt show/hide smoke test passed with that library.
Its SHA256 is `68aa0b68a29a62b6f89ccd753ff52726ef661f37b04405ff42e61ccb9d93131f`.
The build manifest records source, patch and dependency hashes plus actual
library resolution. The installed host Qt remains unchanged.

The VM runner accepts an explicit `--qt-runtime-manifest`. It checks guest
Core/Gui package identities and hashes before installing the candidate RPM,
stages the library separately under guest `/var/tmp`, and runs the regression
again. The application retains the installed RPM launcher; only its launch
environment selects the corrected library. Ordinary app children inherit that
library path; `pkexec` clears it. Pytest and the AT-SPI server do not receive it.
Actual app library mappings are retained for every restart.

The existing X11 base was tested and correctly rejected before candidate
installation: its Qt Core/Gui packages are 6.10.2-2.fc44, incompatible with the
corrected 6.11.2 library. The owned guest was stopped and its overlay reset.
Fresh provisioning with an explicit runtime manifest includes the official
Fedora updates repository during installation, without changing existing bases
or bypassing TLS/package verification. Desktop and reboot results remain pending.

An isolated library is not a distributed corrected Fedora Qt package. The
installed Qt defect and absent deployment qualification remain known
limitations. Native candidate suites are selected according to risk under the
maintainer's revised policy; no native pass is inferred from this library.

The fresh X11 provisioning attempt timed out waiting for the guest agent after
the bounded installation window. It did not reach candidate installation or
desktop tests. The owned incomplete installation was cleaned up by the runner;
unrelated guests and the reusable base were preserved. No new long provisioning
run is required for the local implementation baseline.

## Signed RPM and reboot fixture

The disposable QEMU guest harness builds two inert signed RPM versions and a
signed local repository. Application installation, stale-review rejection,
removal, reinstallation, offline staging, explicit activation and post-reboot
verification use OperationController. Independent RPM inventory, payload,
DNF history, package consistency and preserved-data readbacks are collected.
The independent history oracle requires a new successful transaction, a start
time at or after staging, and separate history details containing the exact
target version. Product verification alone or an empty history list cannot
establish this result.

The fixture is guarded by the dedicated guest marker, QEMU and root checks.
It is integrated into `--reboot-check`; use a fresh guest containing rpm-build,
rpm-sign, GnuPG and createrepo_c. Root harness evidence is backend integration
evidence and does not establish GUI authorization or human desktop usability.

## Reproduction

```bash
LOOFI_IPC_MODE=disabled QT_QPA_PLATFORM=offscreen just verify
just check-packaging
just build-rpm
python3 scripts/qualify_qt_scroll_accessibility.py
python3 scripts/build_qualified_qt_widgets.py
python3 -m e2e.vm test-full --qt-runtime-manifest test-results/v35/qt-runtime/qualification.json --reports-dir test-results/v35/e2e-qt-matchguard
python3 -m e2e.vm test-full --fresh --reboot-check --qt-runtime-manifest test-results/v35/qt-runtime/qualification.json --reports-dir test-results/e2e-v35
python3 -m e2e.vm test-full --fresh --desktop wayland --reboot-check --qt-runtime-manifest test-results/v35/qt-runtime/qualification.json --reports-dir test-results/e2e-v35-wayland
```

No host package installation, source activation, codec installation, commit,
push, publication or release is implied by this report.

## Guide result integrity

Get Fedora ready requires verified saved results for its mutation steps;
reviewed acknowledgement alone does not complete them. Explicit skips remain
available. The backup step is acknowledgement only. GUI and read-only CLI use
the same completion projection. Selected-profile evidence binds the exact
reviewed values to independently successful ActionRuns, including run digests.
It never asserts the current desktop or an entire unselected profile.

The private profile-result domain participates in state inventory and backup.
Legacy guides continue writing version 1; only the new profile-result reference
requires guide version 2. Reading and actual backup/restore of both versions
are covered, including restored proof and ActionRuns. Independent scoped review
passed 64 tests and 30 subtests after correcting the CLI completion count.

## Additional native fixtures

The guest suite includes first Flatpak installation in user/system/named
installations, separate from the retained v34 update matrix. Exact commit,
origin, dependency and unchanged unrelated refs/data are read back independently;
changed-source review rejection is included. `flatpak-install-evidence.json`
records actual guest results when available.

The source/codec setup fixture uses the immutable RPM Fusion Free public key
and signed inert local codec packages. It redirects the exact key download and
the native libdnf5 installroot, and dispatches closed helpers in process through
OperationController. Production guards, trust definitions, signature validation
and transaction execution remain active. Its scope excludes public HTTPS,
desktop Polkit and playback; those are not inferred from backend success.
These fixtures have rootless contract checks; native guest execution is pending.
Native failure cases include a competing source lock in a separate process,
source drift after confirmation and an actual solver conflict between signed
recipe packages. The solver check distinguishes dependency conflict from
unavailable metadata or another backend error. The complete process-death,
network and full-disk native fault matrix remains outstanding.

## RPM application catalog correction

The package now requires Fedora's `appstream-data` catalog. Discovery reports
missing RPM catalogs even when Flatpak results are present. RPM metadata refresh
verifies an actual bounded parseable catalog, independently of readable DNF
package-cache metadata. It explicitly explains that the catalog RPM needs a
separate reviewed package update.

Apps offers explicit Fedora, RPM Fusion Free and RPM Fusion Nonfree catalog
package choices through the existing complete RPM transaction review. None is
preselected. RPM Fusion source configuration remains a separate operation. The
34 focused discovery, metadata and UI tests passed. A themed 720-pixel-wide
large-text check showed readable controls and no horizontal overflow; this is
offscreen layout evidence only.
