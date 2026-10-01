# Release Notes — v30.2.0 "Comfort"

**Release date:** 2026-10-01. Published on GitHub and Fedora 44 COPR.

## Changes

- Extend the tweak catalog from eight to fourteen supported settings.
- Add KDE single/double-click file opening, double-click interval,
  smooth scrolling, and scrollbar click behavior.
- Add GNOME 12/24-hour clock format and clock weekday display.
- Offer explicit restoration of the latest eligible verified Loofi change,
  using saved before/after values and fresh drift checks.
- Preserve exact valid custom numeric values. Block unavailable schemes,
  removed profiles, later attempts, consumed restores, and missing history.
- Report verified saved configuration and explain when KDE applications
  may need reopening.

## Qualification

See the [local qualification report](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/reports/V30.2.0_LOCAL_QUALIFICATION.md)
for the passed local automated and package gates: 4,968 tests, 1,035 subtests,
85.98 percent line coverage, and extracted RPM/source CLI smoke checks.
Physical KDE/GNOME, Traditional/Atomic, manual keyboard, scaling, and audible
Orca checks remain `unverified`. Offscreen results do not prove them.

## Upgrade and authority

No outer schema-v4 migration is required. Runs without restoration metadata
remain readable but cannot offer restoration. Restoration depends on retained
history; pruning can remove its evidence. A successful restore consumes the
offer, and a later normal change creates a new one. There is no redo, bulk
restore, or automatic rollback. Existing routes/action IDs remain readable.

The baseline is v30.1.0 master `737a550`. On 2026-10-01 the user authorized full GitHub, COPR, and wiki publication.
Workstation installation remains outside scope.

## Public verification

The canonical pipeline passed on source `8becbf696fae3d931d7602e05b195cc1850775c8`.
The immutable annotated tag, five GitHub assets, checksums, and attestations
passed independent readback. COPR build `11060103` succeeded for
`fedora-44-x86_64`; the signed package and repository container installation
read back `1:30.2.0-1.fc44` / version `30.2.0`. The public wiki was independently
read back. See the [publication report](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/reports/V30.2.0_RELEASE_PUBLICATION.md).
