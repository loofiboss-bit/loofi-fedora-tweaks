# Architecture — v23.1.0 "Compass"

## Goal

Make the existing six-destination product easier to trust and use while
closing every public host-mutation path behind the existing Action Center.

## Decisions

- Keep `core/public_operations.py` as the machine-readable classification of
  every public CLI and API leaf: `read_only`, `plan_only`, `manual_only`, or
  `mutating`.
- Permit public handlers to inspect state, validate closed parameters, create
  plans, and read plan status. Only an independently confirmed Action Center
  apply request may execute a reviewed plan.
- Reject unknown definitions and arbitrary commands. Operations without a
  safe closed definition fail into explicit manual guidance.
- Preserve Traditional and Atomic Fedora as separate, tested execution and
  verification paths.
- Preserve six top-level destinations, all compatibility routes and aliases,
  lazy page creation, persisted user state, and existing schemas.
- Keep UI presentation in `ui/`; keep planning, classification, and domain
  behavior PyQt-free in `core/` and `services/`.
- Compose the CLI root parser from domain registrars and split MainWindow setup
  into named shell, service, navigation, responsive, and persisted-state
  responsibilities without changing startup order.
- Treat active repository docs as canonical and validate their wiki mirrors.
  Historical release records remain immutable.
- Retain the existing `Compass` metadata value for compatibility; v23.1.0 does
  not introduce a new codename.

## Verification boundary

The release requires zero public direct-mutation findings, full deterministic
tests and coverage, architecture/stabilization/product-contract/drift gates,
privacy-safe real Fedora 44 KDE Wayland screenshots, synchronized release
metadata, a successful RPM build, and independent post-publication readback of
the exact tag, CI, assets, attestations, COPR, installation, docs, and wiki.

Physical Atomic, audible screen-reader, or manual keyboard evidence is never
inferred from automated or Traditional-host checks; any unavailable gate stays
explicitly unverified in the final release record.
