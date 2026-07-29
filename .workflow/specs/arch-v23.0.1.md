# Architecture — v23.0.1 "Compass"

## Goals

- Correct the v23.0.0 daemon user-service sandbox without changing product
  behavior or weakening the rest of the service hardening.

## Decisions

- Keep `ProtectHome=read-only`.
- Permit writes only to `%h/.config/loofi-fedora-tweaks` and
  `%h/.local/share/loofi-fedora-tweaks`, the two existing application-owned
  locations used by the daemon and common launcher.
- Do not change the launcher, daemon protocol, package split, service enablement
  state, or any desktop/system setting.
- Publish a new immutable v23.0.1 tag; never move or overwrite v23.0.0.
