# Everyday qualification

Local candidate verified on 2026-10-07. No publication, installation, new
runtime dependencies, or real settings/removal/update operations were performed.
The application version remains 32.2.0; this document describes the working-tree
candidate, not a published version or the currently installed application.

## Delivered behavior

- Overview prioritizes at most three recorded next steps without starting changes.
- Updates restores persisted pending run identities and verifies without rerunning
  transactions. Invalid or semantically corrupt history is a read error.
- Same-desktop tweak profiles use strict `loofi.tweak-profile/v1` JSON, immutable
  review, current choices, baseline/definition checks, sequential execution,
  cancellation, verification, and existing local restoration history.
- The declarative catalog now has 76 settings, including GNOME left-handed mouse,
  mouse acceleration, and keyboard repeat.
- Installed Apps distinguishes Flatpak installation and full ref, refreshes catalog
  status, shows scoped permissions, and reviews exact removal preserving data.
  Running apps and unreadable inventories block removal. RPM removal uses the
  native software manager. Inventory workers participate in deferred shutdown.
- Dedicated sound and Bluetooth diagnostics use a 15-second session budget,
  cancellation, partial/unknown observations, and closed native settings links.

## Automated evidence

| Check | Result |
|---|---|
| `LOOFI_IPC_MODE=disabled QT_QPA_PLATFORM=offscreen just verify` | PASS: lint, mypy, architecture, generated catalog, version, tests, coverage |
| Full suite | 4,776 passed, 33 skipped, 1,944 subtests passed; 22 warnings |
| Coverage | 85.57%, above the maintained 85% threshold |
| Final focused integration checks | 65 passed, including the additional enlarged-text regression |
| Subsequent Installed view presentation check | 22 passed |
| `just check-packaging` | PASS: requirements, wheel/sdist contents including new modules |
| `just build-rpm` | PASS: Fedora 44 RPM; all eight new domain/service/UI modules present |
| CLI profile apply and app removal help | PASS; explicit installation and confirmation exposed |
| Wiki mirror and `git diff --check` | PASS |
| Independent review | Reported recovery validation, installation-length parity, and session result defects fixed with regression coverage |

The full gate preceded a final visibility adjustment hiding catalog source setup
in Installed mode. The affected 22 tests passed afterward; lint/type checks,
rendering, and RPM build were repeated. Host-changing paths use mocked executors;
these results do not establish physical desktop or authorization-agent behavior.

The RPM is `rpmbuild/RPMS/noarch/loofi-fedora-tweaks-32.2.0-1.fc44.noarch.rpm`.
SHA-256: `21a2450f5e3219b07d4311ed7cc266f829402c14321188759c29856e8f620b89`. This is local build evidence, not installation or repository
signature verification. Existing durable plan/run formats are unchanged.

## Rendering and keyboard evidence

Two completed 225-view matrices cover 25 canonical routes, three themes
(light, dark, high contrast), and three window sizes (900x650, 1280x800,
1600x900). The first uses 100% scaling; the final Installed-view matrix uses
150% scaling with doubled application text. Each view exercises 20 visible
keyboard focus traversals. Final reports show no wrapped-label clipping or
page-level horizontal overflow. The enlarged Installed cards also have a
focused layout regression test. Example inventories and hardware are fixtures.

Reproduce from the repository root:

```sh
LOOFI_IPC_MODE=disabled QT_QPA_PLATFORM=offscreen just verify
just check-packaging
just build-rpm
python3 scripts/sync_wiki_docs.py --check
python3 scripts/capture_control_center_screenshots.py /tmp/everyday-default
python3 scripts/capture_control_center_screenshots.py /tmp/everyday-installed --installed-view --scale 1.5 --large-text
```

## Physical qualification pending

| Surface | Status / required evidence |
|---|---|
| KDE and GNOME sessions | `unverified`: actual changes, portable profile sharing, restore, real reboot continuation |
| Desktop authorization | `unverified`: accept/deny system Flatpak removal through the real agent |
| Flatpak installations | `unverified`: user/system/named installations, preserved real data, running-app handling on dedicated test apps |
| Sound and Bluetooth | `unverified`: actual playback/connectivity and native panels; observations alone cannot confirm operation |
| Assistive technology | `unverified`: screen reader, physical keyboard navigation, desktop scaling |

No active session, installed application, or user settings were changed for this
qualification. Physical checks remain separate from automated/offscreen evidence.
