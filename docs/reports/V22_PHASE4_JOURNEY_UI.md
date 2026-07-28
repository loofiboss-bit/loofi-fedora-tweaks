# V22 Phase 4 — Journey UI matrix

## Automated scope

`scripts/validate_v22_phase4_journey_ui.py` validates the real Qt journey
surfaces Home, System Check, Action Center, and Activity & Recovery in a
16-cell offscreen matrix. Every surface is checked in wide and compact layouts,
LTR and RTL direction, high contrast, 14 pt base text at 200 percent scale,
and the application reduced-motion contract.

The validator checks route activation, named focus targets, Tab progression,
accessible status/control contracts, compact breakpoint selection, and layout
direction. It rejects subprocesses and command-runner execution through the
existing isolated V16 capture harness.

## Physical accessibility gate — not verified by this validator

The following require a real Fedora KDE session and are intentionally not
simulated or claimed by offscreen Qt automation:

- Wayland compositor focus and scaling;
- Orca speech output and keyboard traversal;
- AT-SPI accessibility tree, roles, names, and live-region updates.

Run the physical gate separately with `QT_LINUX_ACCESSIBILITY=1` and the live
AT-SPI validator after the V22 UI implementation is stable.
