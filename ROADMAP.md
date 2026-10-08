# Roadmap

Direction is set by the [product definition](docs/PRODUCT.md). Completed work
is recorded in the [changelog](CHANGELOG.md).

## Local candidate — v32.5.0 "Companion"

KDE and DNF5 are the primary target, with optional GNOME counterparts and
explicitly limited Atomic observations.

- Local built-in/personal profile library with same-desktop review and sharing
- Installed KDE pointer themes, pointer size, and Plasma styles with verified saved values and separate pointer notifications
- Focus, Privacy basics, and Touchpad comfort presets through existing Action Center authority
- Separate Flatpak metadata and override layers with installed permission-tool handoffs
- Saved Health baseline comparison with honest incomplete-source results
- Bounded read-only screen-sharing infrastructure diagnostics
- Editable masked support questions with local Markdown and ZIP export
- Local Fedora upgrade preparation, manual backup checklist, and optional DNF reboot advice

Qualification and remaining physical checks are recorded in
[Companion qualification](docs/COMPANION_VERIFICATION.md). This candidate does
not imply installation, publication, or a broadened Atomic support promise.

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

## Completed — v32.2.0 "Coherence"

- [x] State action-specific recovery and distinguish Loofi standard values from installed defaults
- [x] Bound Tweaks snapshots to 20 seconds with progress, cancellation, schema reuse, and explicit partial results
- [x] Show Flathub availability and installation scope before app review while preserving selections
- [x] Mark local Flathub, RPM Fusion, and Loofi COPR status as complete with manual setup guidance
- [x] Check generated catalog and synchronized version sources in local verification and CI

Physical GNOME behavior, visual effects, keyboard and screen-reader support,
scaling, and Atomic workflows remain unverified for this release. A KDE
Dolphin setting was changed, read back, and restored on the development host;
this does not qualify every setting or the full interface.

## Completed — v32.3.0 "Clarity"

- [x] Modernize the control center's visual presentation and responsive layout
- [x] Improve application icon and desktop-file integration
- [x] Keep the current tweak catalog at 76 verified controls

Physical desktop and assistive-technology qualification remains separate from
automated and rendering evidence.

## v32.4.0 "Care" release

- Installation-scoped app details, reported-size sorting, and source/installation filters
- Optional libflatpak app/runtime support warnings and exact unused-runtime inspection
- Reviewed runtime cleanup through Action Center with drift checks and independent inventory verification
- Source-specific update diagnostics and shared GUI/CLI update observations
- Include the personalization, permission, trust, search, accessibility, and scroll-region improvements from PR #56
- Evidence is recorded in [Care qualification](docs/CARE_VERIFICATION.md)
- Physical KDE, GNOME, assistive-technology, and real-session Polkit qualification remains separate

The tag-driven release workflow publishes the GitHub assets and COPR package
after the master validation, package, and smoke-test gates pass.

## Included candidate work — Personalization and app insight

- [x] Add Reduced motion and File navigation presets through existing profile review and Action Center execution
- [x] Add an eight-second, one-setting inspection and refresh after a single change or restore
- [x] Show installation-bound Flatpak metadata permissions in the GUI and CLI
- [x] Complete full automated, packaging, and responsive rendering verification
- [ ] Physical KDE, GNOME, and assistive-technology qualification

Included in Care; physical desktop and assistive-technology qualification
remains unverified.

## Prior local work — Control center redesign

- [x] Loofi design system and system-selected light/dark presentation
- [x] Overview start route, Activity navigation, and explicit Tools disclosure
- [x] Shared asynchronous resource and hardware snapshots with honest availability
- [x] Unified task pages, controls, and operation feedback
- [x] Complete automated, rendering, and packaging qualification
- [ ] Physical KDE, then GNOME and assistive-technology qualification

No public release or local installation is implied. Physical desktop,
assistive-technology, and unavailable hardware evidence remain separate.

## Prior local work — Everyday

- [x] Prioritized Overview next steps from recorded observations
- [x] Restore pending update verification after application or computer restart
- [x] Same-desktop, file-based tweak profiles with immutable sequential review
- [x] Three additional GNOME controls (76 catalog settings)
- [x] Scoped installed Flatpak inventory and reviewed removal preserving data
- [x] Dedicated read-only sound and Bluetooth diagnostics
- [x] GUI and CLI entry points with shared operation authority
- [ ] Physical KDE, GNOME, and assistive-technology qualification

See [Everyday qualification](docs/EVERYDAY_VERIFICATION.md) for local evidence.
No publication or installation is implied.

## Later

- Additional DNF configuration after a specific user need and safe verification
  contract are established.
- Additional Fedora spins and Atomic desktops, as qualification allows

## Not planned

Background monitoring while views are hidden, mesh/network sharing, AI features,
and a plugin marketplace.
