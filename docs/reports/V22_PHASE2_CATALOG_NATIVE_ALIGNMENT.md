# V22 Phase 2 — Catalog and native alignment

## Outcome

Phase 2 passed its local gate on 2026-07-28.

- The catalog authority composes destination-owned typed record modules.
- The V20 continuity transformation layer was removed only after exact
  projection and ordering checks passed for all 81 routes.
- `CapabilityState` exposes the six inert presentation states defined by the
  V22 architecture.
- Five opaque `NativeHandoffId` values map to one fixed allowlist owned by a
  PyQt-free service.
- Discover and KDE KCM launches are non-privileged, user-initiated, ephemeral,
  and revalidated immediately before `QProcess.startDetached`.
- Missing executables and exact KCM identifiers produce truthful unavailable
  presentation without executing a fallback command.

## Verification

- 98 catalog, navigation, compatibility, persistence, and native-handoff tests
  passed.
- `just validate-architecture` passed.
- `just validate-product-contract` passed with exactly 81 routes.
- `just lint`, `just typecheck`, and `git diff --check` passed.

The checks perform no cold-start native probe and introduce no timer or
`QThread`.
