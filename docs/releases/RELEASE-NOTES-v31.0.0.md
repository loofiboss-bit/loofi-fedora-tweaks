# Release Notes — v31.0.0 "Mastery"

**Release date:** 2026-10-02.

## Summary

Loofi Fedora Tweaks v31.0.0 "Mastery" delivers full command-line interface (CLI) parity
with the graphical interface, extends the curated desktop tweak catalog to 22 verified controls
across GNOME, KDE, and privileged system settings (DNF5), integrates dynamic package manager
resolution for packaging maintenance, adds new productivity and utility applications, and
streamlines GUI search interactions.

## Highlights & Features

### 1. Expanded Tweak Catalog (14 → 22 Controls)
- **GNOME Desktop**:
  - Window titlebar buttons (`gnome-button-layout`): Close only, Minimize/Maximize/Close, Left-side controls.
  - Touchpad tap-to-click (`gnome-tap-to-click`): Enable/disable touchpad tap to click.
  - Night Light (`gnome-night-light`): Warm display colors at night to reduce eye strain.
  - Sound over-amplification (`gnome-sound-overamp`): Allow volume above 100% in volume controls.
  - Font antialiasing (`gnome-font-antialiasing`): Subpixel LCD (ClearType), Grayscale, None.
- **KDE Plasma**:
  - Touchpad tap-to-click (`kde-tap-to-click`): Configured via `kcminputrc`.
  - Night Color (`kde-night-color`): Configured via `kwinrc`.
- **System & Packaging**:
  - DNF parallel downloads (`dnf-parallel-downloads`): Accelerate package downloads with choices (3, 5, 10, 15), Polkit elevation, and read-only `--dump-main-config` inspection. Automatically unavailable on Atomic Fedora.

### 2. Full CLI Parity: `tweaks` and `apps`
- Native `loofi tweaks` subcommands:
  - `loofi tweaks list`: Tabular list of available tweaks, current values, and restoration availability.
  - `loofi tweaks get <id>`: Detailed view of a specific tweak with all supported options.
  - `loofi tweaks set <id> <value>`: Apply a setting change with confirmation and `--dry-run` preview.
  - `loofi tweaks restore <id>`: Restore previous verified value from a specific run (`--from-run`).
- Native `loofi apps` subcommands:
  - `loofi apps list`: Tabular overview of curated applications, categories, and sources.
  - `loofi apps install <id>`: Install application with `--dry-run` preflight and validation.
- Standard JSON output supported across all subcommands via `--json`.

### 3. Dynamic Package Manager Resolution
- Catalog clean actions (`dnf-clean-all`) now query the detected runtime package manager (`runtime.package_manager()`) rather than invoking hardcoded binary paths.

### 4. Application Catalog Additions
- Added Flatseal (Flatpak permission manager), Mission Center (hardware & resource monitor), Spotify (music streaming), and Neovim (modern Vim-fork terminal text editor).

### 5. UI Search Usability
- Group cards on the Tweaks page now dynamically hide when all child rows are filtered out by the active search query.
