# v33.0.1 Concord — release qualification

The Concord implementation was merged in PR #68 at `f8e3e7e`. Its product
behavior was qualified as the v33.0.0 candidate; the release package version
is 33.0.1 because the existing v33.0.0 tag names the older Bastion source.
The version-only package change passed packaging gates. v33.0.1 was published
on 2026-10-12; [publication evidence](reports/V33.0.1_RELEASE_PUBLICATION.md)
records exact lineage and the explicit VM qualification exception.

## Delivered behavior

Overview leads with CPU, RAM, GPU, and storage. Tweaks contains Settings and
Profiles, preserves profile drafts across navigation, and chains inspection,
editing, saving, and review only after a worker's captured terminal result.
Failed or cancelled saves never open review. Apps contains Catalog, Installed,
and Sources; selected apps remain editable independently of search filters,
and review exposes package identity, source, and installation scope directly.
Operations retain their origin and individual result links across navigation.
Only actual run IDs produce Activity links. Existing routes, CLI/JSON,
profile format, history schema, and execution ownership remain unchanged.

## Stable Fedora KDE test execution

The initial failures were traced to changed UI contracts and native Qt
accessibility behavior, rather than bypassed with retries:

- Focus the containing application tab list, send native arrow keys, and
  verify the selected tab; virtual child-tab focus is insufficient.
- Expose the guide popup as an accessible child with native focus actions.
  Select the exact named next step rather than positional menu keystrokes.
- Start Installed Refresh explicitly and observe its real busy cycle. Reset
  the Apps scroll position after a subview change so controls remain visible.
- Verify Requested and Verified values on the exact setting-status row,
  including restoration and session activation, alongside independent KDE
  and DNF configuration readback.
- Move operation workers to their completion thread before emitting terminal
  signals, preventing completion and shutdown from racing thread affinity.
- Print run status and bounded, credential-redacted failure diagnostics;
  retain separate normal and after-reboot evidence and disposable-disk cleanup.

Host regressions cover invalid tab paths, focus failure, missing selected
state, incorrect result feedback, refresh cancellation, late worker replies,
profile draft/save/review failure, exact Activity targets, and selection that
survives filters. See [the runner contract](E2E_VM_TESTS.md).

## Evidence and limitations

`just verify` passed: lint, typing, architecture rules, catalog/version
contracts, 5,382 tests and 2,154 subtests; 33 tests were skipped and coverage
was 85.49%. `just check-packaging` passed the dependency and wheel/sdist
manifest checks on the 33.0.1 candidate.

The final rendering matrix includes the active guide control: 1,008 captures
across light, dark, and high-contrast themes; 900×650, 1280×800, and 1600×900;
100%, 150%, and 200% scaling plus enlarged text. Automated checks found no
wrapped-label clipping, control-text clipping, stale table themes, or
horizontal overflow. CPU, RAM, GPU, and storage were visible without scrolling
at 1280×800 at normal scale. The 24-case offscreen review-dialog matrix passed
scope disclosure, accessible names, keyboard acceptance/cancellation, and
bounded layout checks.

The final 500-row synthetic search measurement used 30 samples: p95 was
45.37 ms against the 150 ms target. Twenty alternating fresh-process startup
pairs against `a62f6e7` had a median change of −5.63%. Earlier independent
20-pair measurements were +1.95%, −0.31%, and −0.69%; no reproducible median
regression above 10% was observed. These are offscreen, mocked measurements,
not physical desktop or cold-cache startup qualification.

Current artifacts are written under `test-results/v33/`, `test-results/e2e/`,
and `test-results/e2e-reboot/`. VM summaries record the exact tested RPM SHA-256;
JUnit and pytest logs retain the individual test results. These are local
generated evidence, not published release assets.

The normal Fedora 44 KDE/X11 run passed 9 tests, with 2 intentionally skipped
reboot checkpoints. It exercised guide persistence, Discover handoff and
refresh, personal setting change/readback/restore, denied and approved Polkit,
DNF5 readback, application restart, navigation, and inert local RPM
installation/removal. The owned guest was stopped and its overlay discarded.

A second clean-overlay run, `just test-full-reboot`, passed 10 tests before
reboot (1 intentionally skipped after-reboot checkpoint) and 1 test after
reboot (1 intentionally skipped preparation checkpoint). The runner recorded
different guest boot IDs. The saved Dolphin value and exact guide state
survived reboot; restoration agreed with an independent KDE reader afterward.
The VM runs repeated the normal workflows on the final product source and add
actual guest reboot evidence. They used the v33.0.0 candidate; the subsequent
33.0.1 source change only updates release-version metadata and documentation.
The host-memory preflight initially refused this
additional run; after memory was freed, it passed with the original 6 GiB
threshold. No memory safety threshold was reduced. The guest was stopped and
its disposable overlay restored after the successful run.

Both runs used the protected reusable Fedora 44 KDE/X11 base, offline
networking, 5 GiB RAM, and 2 vCPUs. They qualify disposable-overlay execution,
not a new installation of the base image. `just build-rpm` passed for
33.0.1-1.fc44. The GitHub release pipeline rebuilds, smokes, and reviews the
exact release RPM. Canonical release run 38183736156 passed all other gates
with VM E2E explicitly waived. The public RPM SHA-256 is
`3db7b7871cf64e36e7b32e7d34b68325b9d82eb31cc25821778ce9e18c04e7d6`.

Physical hardware, human screen-reader use, Wayland input, GNOME, and Atomic
workflows are not qualified by these results. Offscreen rendering and Qt
keyboard checks do not establish physical desktop or screen-reader behavior.

## Manual v33.0.1 publication exception

On 2026-10-12 the maintainer authorized completing GitHub and COPR publication
without further VM E2E investigation. Exact candidate CI run 38178492268 failed
with an AT-SPI/WebDriver timeout (5 passed, 1 failed); release run 38178492259
failed after a guest Python general protection fault in libQt6Gui.so.6.10.2
(4 passed, 1 failed). Both runners stopped the guest and discarded test changes.
The crash root cause is unresolved. These results do not qualify the exact
33.0.1 GUI payload. The manual workflow exception is restricted to 33.0.1
and preserves every other build, review, test, evidence, and publication gate.
