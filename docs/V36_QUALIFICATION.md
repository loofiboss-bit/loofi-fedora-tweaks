# v36.1.0 Blueprint qualification

This records local qualification evidence for the v36.1.0 candidate. It does
not establish a published release. Automated, virtual-machine, Qt runtime, and
physical desktop evidence are reported separately.

## Automated checks

- `just verify`: passed, 5,845 tests, 33 skipped, 2,440 subtests, 22 warnings,
  and 85.08% coverage on October 24, 2026. Required coverage is 85%.
- Focused setup and E2E kickstart regressions: 68 passed, including the local
  hard-process-exit/reconciliation regression. The kickstart contract
  tests alone passed 39 cases after the guest service-ordering fixes.
- `just check-packaging`: passed dependency synchronization and wheel/sdist
  packaging checks.
- `just build-rpm`: passed for `loofi-fedora-tweaks-36.1.0-1.fc44.noarch.rpm`.
  This is a local unsigned RPM; it has not been published.
- Setup application filtering: 5,000 synthetic rows, 200 local search updates,
  median 6.96 ms and p95 11.58 ms. This meets the 150 ms p95 target. The
  offscreen sample ran while a separate Fedora VM was installing packages, so
  the measured latency includes host contention.
- Large-text setup UI: an 18 pt offscreen view at 700×650 with 20 apps showed
  app rows without horizontal scrolling. Keyboard Tab moved from Overview to
  the computer-read action, and vertical scrolling reached the save controls.

## Isolated Fedora KDE guest

The reusable Fedora 44 image lacks the current `python3-libdnf5` dependency.
Fresh provisioning needed several kickstart and guest-channel fixes before a
clean KDE/X11 base completed installation and started KDE plus the guest agent.
The candidate RPM installed, and the Blueprint guest test reached its restart
fixture. That fixture's path type was fixed, but the next run stopped at host
preflight: 5,353 MiB was available against the runner's 6,144 MiB requirement.
No guest Blueprint pass is inferred.

To avoid repeating VM provisioning for persistence logic, the host suite now
includes `test_hard_process_exit_reopens_and_reconciles_before_a_new_review`.
It uses a temporary library and progress store, terminates a child process
after durable step updates, reopens the store, reconciles against a fresh fake
inventory, and starts a new review for only the unfinished app. This exercises
the crash/restart contract without guest provisioning, network access, or
system package changes. The isolated guest still provides separate Fedora KDE
coverage when host resources permit; the current run did not qualify its GUI
or package integration behavior. Earlier guest reports are under
`test-results/e2e-fresh/fresh-x11-d63f6ba4030b`.

## Qt accessibility runtime boundary

`python3 scripts/qualify_qt_scroll_accessibility.py` was run on October 24.
The installed Qt 6.11.2 runtime still accepts a stale accessibility child
index after hiding a scroll area; the isolated process exited `-11` with three
visible children, one hidden child, and a request for prior index 2. This
reproduces the known Qt runtime defect separately from Fedora Tweaks checks.
Accessibility remains enabled, and no host Qt package was changed.

Physical KDE usability, hardware behavior, and human screen-reader use were not
qualified by offscreen or virtual-machine checks.

## Reproduction

```bash
just verify
just check-packaging
just build-rpm
python3 scripts/qualify_qt_scroll_accessibility.py
python3 -m pytest -q tests/test_setup_configurations.py tests/test_setup_orchestration.py
```

The fresh guest is isolated from the reusable base. Local qualification does
not imply a commit, tag, signature, publication, or release.
