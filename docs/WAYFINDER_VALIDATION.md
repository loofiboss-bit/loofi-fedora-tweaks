# Wayfinder local qualification

Candidate: **32.1.0 Wayfinder**, RPM **1:32.1.0-2.fc44.noarch**.
Scope: source, package, and local installation. No public publication is included.

## Automated gates

- `just verify`: lint, mypy, architecture checks, complete tests and 85% coverage gate.
- `python3 scripts/gen_tweaks_doc.py --check`: generated 73-control catalog.
- `python3 scripts/bump_version.py --check` and same-version `--dry-run`:
  active sources agree; no retired scripts or workflow scaffolding required.
- `just build-rpm` and `just check-packaging`: local RPM and package manifest.
- `git diff --check`: whitespace and conflict-marker review.

Final result: **4,586 passed, 33 skipped**, 1,856 subtests passed,
**85.45% coverage**. Lint, mypy, architecture, generated catalog, active version,
RPM build, and packaging manifest gates passed.

## Rendering and keyboard checks

The real PyQt shell was rendered with isolated app settings and a fixed KDE
profile. Six views (Tweaks, Apps, Updates, Health, Settings, History & Undo) were
captured at **900x650** and **1280x800 logical pixels**, at Qt scale factors
**1.0, 1.5, 2.0**. Light, dark, and high contrast Tweaks captures add nine
checks to the 36 main-view captures. Each capture exercised 20 focus traversals
and required focused widgets to remain visible. Fixture geometry regression
also checks setting editors and row actions at 560, 900, and 1280 pixels.

Review found and fixed collapsed setting controls, inaccessible Settings
sections, missing selected-filter emphasis, and low-contrast favorite/header
icons. Selected-control foreground/background contrast is at least 5:1 across
system, light, dark, and high contrast palettes on this host.

Repository artifacts are generated source screenshots, not photographs of the
live desktop. See [screenshot instructions](images/README.md).

## Live KDE configuration and session readback

Four new Dolphin controls passed a real CLI change, independent saved readback,
history-bound restore, and final readback. Their prior values were restored:
editable location=false, remembered tabs=true, external folders in new tabs=false,
and confirmation when closing multiple tabs=true.

Edge tiling, focus stealing prevention, and maximized titlebar controls passed
real change and restoration cycles, including saved and active KWin values.
The final values are respectively true, 1 (Low), and false. KWin was never
restarted. Runtime qualification found the ordinary executor output truncation
and the asynchronous reconfigure race; the fixes retain a bounded exact-command
read and only retry runtime reads on a valid mismatch.

Private app-settings and desktop-configuration backups were made before host
changes. The settings file is compared across package installation; action
history/logs legitimately gain verification records from these checks.

## Explicit qualification limits

- Physical Dolphin window behavior and visual desktop interaction: **unverified**.
- Physical GNOME session: **unverified**; Nautilus schema is absent on this KDE host.
- Screen reader interaction: **unverified**.
- Offscreen rendering and keyboard tests do not establish these physical checks.

## Local installation readback

The exact local DNF transaction was simulated with `--cacheonly --assumeno`:
one package upgrade, no dependency changes or downloads. The expected
assumeno cancellation prevented any mutation during simulation. The subsequent
confirmed local install completed successfully.

- Installed NEVRA: **1:32.1.0-2.fc44.noarch**.
- `rpm -V loofi-fedora-tweaks`: no discrepancies.
- Installed CLI: version 32.1.0, codename Wayfinder; 30 applicable KDE/shared controls.
- All seven exercised file/window controls are ready and retain their original values.
- Critical installed source files match the verified checkout by SHA-256.
- The app settings file is byte-for-byte unchanged across verification and installation.
- `dnf5 --cacheonly check`: local package consistency passed; no live repository refresh.
- No running Loofi application needed termination. This local qualification did not publish a release; PR preparation is a separate step.

RPM SHA-256: `97c19f6a4bf21aeeee5721b28c91548b0fdfec6437fa0f50f0e2fa7fa525b67f`.

Private backup: `~/.local/state/loofi-fedora-tweaks-backups/32.1.0-2-20261004-162343`.
The manifest and copies are kept locally; personal configuration is not included
in repository artifacts.
