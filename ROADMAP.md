# Roadmap

Direction is set by the [product definition](docs/PRODUCT.md). Completed work
is recorded in the [changelog](CHANGELOG.md).

## Completed — v32 "Refocus" (released as v32.0.2)

Give the application a clear purpose: tweaks first.

- [x] Product definition and simplified documentation
- [x] Retire the release-evidence tooling that was not part of the product
- [x] One navigation model with Tweaks as the start page
- [x] Simple mode by default; advanced tools behind one switch
- [x] Remove hidden pages, dead modules, and unused CLI domains
- [x] Data-driven tweak catalog, growing from 22 to 50+ tweaks
- [x] Per-tweak reset to default, undo, and "changed from default" filter

## Completed — v32.1.0 "Wayfinder" (released)

- [x] Add GNOME Files click behavior and default folder view controls
- [x] Add Dolphin full-path and KWin maximized-titlebar controls
- [x] Keep catalog docs generated and align architecture, release, and version guidance
- [x] Limit version management to the three active version sources
- [x] Add four Dolphin, two KWin, and two GNOME Files settings (73 controls)
- [x] Add semantic controls, compound filters, persistent favorites, and explicit pending values
- [x] Redesign Apps, Updates, Health, Settings, and History & Undo
- [x] Add separate verified KWin session activation through Action Center
- [x] Complete candidate verification, RPM release 2, and local upgrade

Physical GNOME, KDE, assistive-technology, and live visual qualification remain
unverified and are tracked separately in
[Wayfinder validation](docs/WAYFINDER_VALIDATION.md).

## Next

- Show read-only local status and setup guidance for Flathub, RPM Fusion, and
  Loofi COPR. Source changes and codec installation remain manual-only.

## Later

- Additional DNF configuration after a specific user need and safe verification
  contract are established.
- Shareable tweak profiles (export and re-apply), pending a separate product
  scope decision.
- Additional Fedora spins and Atomic desktops, as qualification allows

## Not planned

System monitoring as a headline feature, mesh/network sharing, AI features,
and a plugin marketplace.
