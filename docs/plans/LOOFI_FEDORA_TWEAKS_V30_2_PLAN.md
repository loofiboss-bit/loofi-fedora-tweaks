# Loofi Fedora Tweaks v30.2.0 "Comfort" — Implementation Plan

## Goal and authority

Deliver Comfort from v30.1.0 master commit `737a550`.
Keep Home, Apps, Tweaks, Health, and Updates and the existing Action Center
mutation authority. Local implementation has been qualified. On 2026-10-01
the user authorized commit, push, canonical GitHub/COPR publication, and public
wiki synchronization. Workstation installation remains outside scope.

## Settings

Extend the closed catalog to fourteen controls (seven KDE, eight GNOME).
KDE uses group `KDE` in `kdeglobals`: `SingleClick` (boolean),
`DoubleClickInterval` (200/400/600/800 ms; valid range 100–2000), `SmoothScroll`
(boolean), and `ScrollbarLeftClickNavigatesByPage` (boolean). GNOME uses
`org.gnome.desktop.interface` keys `clock-format` (`12h`/`24h`) and
`clock-show-weekday` (boolean). Missing readers/writers and unreadable values
must explain their unavailable state and block mutation.

## Restoration

Add a setter for each new tweak and one `restore-*` action per catalog tweak.
Restore input contains only `source_run_id`. Resolve the setting and exact
previous value from versioned metadata stored in existing
`verification_result.data`, keeping the outer schema-v4 format and atomic store.
Only the latest verified normal change with complete evidence is eligible.
Re-read during preflight and require current value to match its saved after
value. Reject later change attempts, external drift, consumed restores,
legacy/pruned history, and unavailable schemes/profiles. Preserve exact valid
custom numeric values. Show current/previous values in a compact confirmation.
Restore through a new independently verified run; success consumes the offer.
Do not add bulk restoration, redo, profiles, or automatic rollback.

## Verification and delivery

Cover all controls, valid/invalid values, missing tools, failed readback,
Traditional/Atomic GNOME/KDE, unknown/bootc blocking, and restore persistence,
precision, drift, legacy history, cancellation, timeout, and storage failures.
Verify UI truthful outcomes and overlapping-operation blocking.
Run `just verify` (85% coverage), `just validate-release`, `just stats-check`,
`just check-drift`, `just check-packaging`, and `git diff --check`. Build RPM and
source package and inspect version and packaged CLI. Record physical KDE,
GNOME, keyboard, scaling, and Orca checks independently as `unverified` until
performed. Sync active guides and the repository-owned wiki mirror. Report
saved KDE configuration without guaranteeing active effects in open programs.

### Custom scalar restoration bounds

Restoration preserves the captured scalar without display rounding. GNOME text
scale must be between 0.5 and 3; KDE animation duration must be finite and
nonnegative; KDE double-click interval must be an integer between 100 and
2000 ms. These custom values come only from verified saved evidence, not
arbitrary caller input. Invalid or unreadable values block modification.
