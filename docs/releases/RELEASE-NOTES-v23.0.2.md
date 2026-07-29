# Release Notes -- v23.0.2 "Compass"

**Release Date:** 2026-07-29

**Codename:** Compass

**Theme:** Complete the daemon's bounded systemd state contract

## Summary

Compass v23.0.2 completes the packaged background daemon's hardened systemd
state contract. The service now receives private, application-owned runtime
and log-state directories while the operating system and the rest of the
user's home directory remain read-only.

## Highlights

- Restores startup health collection under the real user-service sandbox.
- Restores the rotating application log under the XDG state directory.
- Uses systemd-managed directories with mode `0700`.
- Retains `ProtectSystem=strict` and `ProtectHome=read-only`.

## Changes

### Fixed

- Added `RuntimeDirectory=loofi-fedora-tweaks` for the collector lease under
  `$XDG_RUNTIME_DIR`.
- Added `StateDirectory=loofi-fedora-tweaks` for `app.log` under
  `$XDG_STATE_HOME`.
- Kept the explicit writable config and data paths introduced by v23.0.1.

## Safety and compatibility

- No route, schema, CLI, API, daemon protocol, dependency, or repair-authority
  changes.
- Existing settings and state remain in place.
- Installation and upgrade do not enable services or apply desktop or system
  settings.
- v23.0.0 and v23.0.1 remain immutable as their exact published and attested
  releases.

## Upgrade Notes

Upgrade all installed subpackages together. No user-data migration or manual
configuration change is required.

## Publication verification

- Annotated tag `v23.0.2` peels to exact commit
  `8d0a94eec17586ff2b0101ad460083fbf26ef9b7`.
- Auto Release Pipeline `30461966230`, CI `30461966951`, and CodeQL
  `30461966045` completed successfully.
- Eight GitHub release assets passed fresh checksum and attestation readback.
- COPR build `10788467` reached terminal `succeeded`; all three signed public
  RPMs expose `1:23.0.2-1.fc44`.
- A clean Fedora 44 public-repository installation and a real Fedora 44 host
  upgrade passed package, D-Bus health, runtime/state, and user-configuration
  preservation checks.

See [V23 public release evidence](../reports/V23_RELEASE_PUBLICATION.md) for
the complete boundary and the explicitly authorized physical skips.
