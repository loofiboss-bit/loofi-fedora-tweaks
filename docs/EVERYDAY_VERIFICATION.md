# Everyday product verification

This local working-tree candidate is based on reviewed commit `63c47bc` on
`codex/personalization-app-insights`. The package version remains `32.3.0`;
version files were not changed. Its local RPM was reinstalled on Fedora 44
through a DNF5 transaction scoped to this package. No app-scoped user files
changed, and no release was published.

## Delivered behavior

- Security observations distinguish complete, unavailable, failed, and stale
  data. Incomplete port or firewall checks do not produce a zero-port result or
  numeric assessment.
- Review dialogs default to Cancel and bind Escape to cancellation. Settings
  changes restore saved state after persistence failure; Loofi logging and
  notification preferences apply consistently.
- The opt-in Loofi version check runs asynchronously after the first window
  appears, with a four-second network timeout. It reads version metadata only,
  and reports offline/cache status in the app without downloading or installing
  anything.
- Global search projects current-platform settings from the canonical catalog
  and navigates without changing values. Installed search filters the captured
  inventory while preserving each installation identity.
- Overview offers dismissible, platform-relevant first steps. Health checks are
  read-only and symptom-led. Activity loads up to 25 local Loofi runs on first
  visit, with exact lookup for linked runs outside that page.
- Update review retains candidate names and versions, caps each source at 100
  entries, reports omitted and stale results, and shows the observation time and
  transaction caveat.

## Automated verification

| Check | Result |
|---|---|
| `LOOFI_IPC_MODE=disabled QT_QPA_PLATFORM=offscreen just verify` | PASS: lint, mypy, architecture, catalog/version checks, tests, and coverage |
| Full suite | 4,823 passed, 33 skipped, 1,945 subtests passed; 22 warnings |
| Coverage | 85.09%, above the maintained 85% threshold |
| `just check-packaging` | PASS |
| `just build-rpm` | PASS: `loofi-fedora-tweaks-1:32.3.0-1.fc44.noarch` |
| RPM artifact | `rpmbuild/RPMS/noarch/loofi-fedora-tweaks-32.3.0-1.fc44.noarch.rpm`, 4,280,504 bytes |
| RPM SHA-256 | `06384517807097f6f82cec65988e6b650413062984f89719a023438a73ba1a05` |
| Fedora 44 local install | PASS: DNF5 simulation and transaction contained only this package |
| Installed package integrity | PASS: `rpm -V`; installed `%{SHA256HEADER}` matches the candidate |
| Package-manager consistency | PASS: `dnf5 --cacheonly check` |
| Installed launcher smoke | PASS: version and CLI `info`; offscreen GUI stayed running for 4 seconds with temporary XDG roots |
| App-scoped user state | PASS: all 44 recorded files and metadata unchanged after reinstall |
| Rootless Fedora 44 package smoke | PASS: install, `rpm -V`, header identity, CLI version/info/doctor as an unprivileged user; doctor exit 0 |
| Rendering and keyboard matrix | Four 225-view matrices; details below |

The local DNF5 transaction reinstalled only `loofi-fedora-tweaks`. DNF reported
that it skipped OpenPGP checks for the local command-line RPM, so its signature
is unverified. The rootless container smoke independently installed the same
RPM, confirmed its header identity and file integrity, and exercised the CLI as
a regular user.

Each rendering matrix covers 25 routes, light/dark/high-contrast themes, and
900×650, 1280×800, and 1600×900 windows. Runs cover 100%, 150%, and 200%
scaling plus doubled application text. All four report zero clipped wrapped
labels, control text, or table text; zero stale table theme colors; and zero
page-level horizontal overflow. Each rendered view completes 20 visible
keyboard-focus traversals.

The matrix measures offscreen presentation with fixture data. It does not
qualify physical scaling, desktop integration, screen readers, system tray
behavior, or real authorization prompts.

Reproduce the visual checks from the repository root:

```sh
LOOFI_IPC_MODE=disabled QT_QPA_PLATFORM=offscreen PYTHONPATH=loofi-fedora-tweaks python3 scripts/capture_control_center_screenshots.py /tmp/everyday-100 --scale 1 --installed-view
LOOFI_IPC_MODE=disabled QT_QPA_PLATFORM=offscreen PYTHONPATH=loofi-fedora-tweaks python3 scripts/capture_control_center_screenshots.py /tmp/everyday-150 --scale 1.5 --installed-view
LOOFI_IPC_MODE=disabled QT_QPA_PLATFORM=offscreen PYTHONPATH=loofi-fedora-tweaks python3 scripts/capture_control_center_screenshots.py /tmp/everyday-200 --scale 2 --installed-view
LOOFI_IPC_MODE=disabled QT_QPA_PLATFORM=offscreen PYTHONPATH=loofi-fedora-tweaks python3 scripts/capture_control_center_screenshots.py /tmp/everyday-large --scale 1 --large-text --installed-view
```

## Scroll-spacing regression follow-up

The supplied KDE recording exposed oversized empty regions in Tweaks and
Health. Cards and content columns now allow vertical shrinkage at the assigned
width. Health lays out only its visible workflow view, so hidden Results no
longer pushes maintenance below empty space.

Regression coverage checks Tweaks filtering and resize transitions at 900×650,
1280×800, and 1600×900, plus Health view switching and active-view height.
Rendering captures wait for queued layouts after replacing state-backed
editors, matching the existing settling period after route activation.
The final follow-up gate passed 4,825 tests and 1,945 subtests, with 33
skipped tests and 85.19% coverage. All four repeated rendering matrices
(900 views total) report zero clipped text, stale table colors, or horizontal
overflow. Packaging checks and the RPM build passed. Physical confirmation
of this follow-up remains `unverified`.

## Physical qualification pending

| Surface | Status / required evidence |
|---|---|
| KDE, then GNOME | `unverified`: real settings, system tray, session preservation, and recovery |
| Screen reader and keyboard | `unverified`: physical focus order, names, announcements, and scaled desktop text |
| Authorization | `unverified`: accepted and denied prompts in a separate test environment |
| Package operations | `unverified`: update/removal transaction; the same-version reinstall and state readback passed above |

The reinstall replaced the application's system payload but changed none of
the recorded app-scoped user files. Offscreen checks do not establish physical
desktop behavior; those checks remain separate from automated evidence.
