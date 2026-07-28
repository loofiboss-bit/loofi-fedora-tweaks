# Architecture — v22.0.0 "Alignment"

## Goal

Consolidate the existing safe Fedora control center around enforceable trust
gates, one canonical product catalog, explicit capability presentation,
allowlisted native desktop handoffs, and a quieter task hierarchy without
changing public execution authority.

## Decisions

- Product catalog records become destination-owned modules composed by
  `core.product_catalog`. Route identity and order are equality-gated before
  the V20 continuity transformation may be retired.
- `CapabilityState` is inert presentation data. It never authorizes execution,
  probes the host during catalog construction, or creates persistence.
- `NativeHandoffId` is opaque outside the native-handoff service. The service
  owns a fixed allowlist, availability checks, bounded non-privileged launch,
  and structured result reporting.
- `ApplicationRuntime` owns a two-phase resource protocol: request every
  resource to stop, then wait against one shared deadline. Immediate cleanup is
  allowed only for operations documented as non-blocking.
- COPR workflow state is explicit. Terminal API success, repository
  availability, clean package installation, and installed-version readback are
  separate mandatory facts; result artifacts remain diagnostic.
- Support evidence redaction applies at the shared privacy boundary before
  journal or generated content is written to an export.
- The current PyQt6 semantic token system remains the design authority.
  Alignment repairs hierarchy and task density rather than introducing a new
  visual language.

## Native handoffs

| ID | Target |
| --- | --- |
| `plasma.discover` | `plasma-discover` |
| `plasma.network.connections` | `kcmshell6 kcm_networkmanagement` |
| `plasma.appearance` | `kcmshell6 kcm_lookandfeel` |
| `plasma.display` | `kcmshell6 kcm_kscreen` |
| `plasma.window.management` | `kcmshell6 kcm_kwinoptions` |

The catalog stores only the handoff ID. Missing executables or KCMs produce a
truthful unavailable/manual presentation. Handoffs are user-triggered, use no
`pkexec`, and never run during startup.

## Protected behavior

- Preserve all 81 routes, aliases, favorites, settings, direct links, lazy
  loading, and the one-provider startup contract.
- Preserve Action Center schema v4 and its plan, confirmation, execution,
  verification, lease, reboot, and fail-closed policies.
- Preserve System Check, journal, CLI/API/daemon/D-Bus, Traditional/Atomic, and
  future-schema contracts.
- Keep the API loopback-only and non-mutating.
- Keep Fedora 44 stable and Fedora 45 preview-only during implementation.
- Do not physically split Specialist Tools packaging.

## Phase gates

- Phase 0 changes authority and evidence only.
- Each implementation phase passes focused tests plus architecture, product,
  route, release-document, startup, and coverage gates before the next begins.
- Product metadata remains v21.0.0 during implementation. Version changes,
  commit, push, tag, publication, installation, and public readback are
  release-only actions.

