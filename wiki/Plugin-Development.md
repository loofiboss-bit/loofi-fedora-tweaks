# Built-in Provider Development — v27.0.1 "Core"

The external Python Plugin SDK, public Marketplace, and third-party extension
execution are retired. This page documents the internal, main-repository
provider contract only.

## Canonical catalog

`core.product_catalog` owns reviewed route, destination, capability, risk, and
handoff metadata. Do not add a second registry or a public plugin loader.
Compatibility projections may remain for migration, but they cannot import or
execute user-provided code.

## Provider requirements

Every built-in provider must:

- ship in the reviewed application source tree;
- keep PyQt6 presentation in `ui/` and domain logic in `core/` or `services/`;
- defer widget construction until route activation;
- classify operations as `host`, `app_state`, `session`, or `manual_only`;
- send persistent host changes through `ActionCenterOrchestrator`;
- use typed availability and deterministic tests for route and capability
  behavior.

UI code must not call subprocesses, select package managers, or mutate files.
Unknown Fedora desktop/session/backend capabilities remain unavailable.

## Action definitions

An Action Center definition declares a closed parameter schema, affected
resources, preflight, preview, authorization, reboot expectation,
independent verification, and recovery guidance. Unsupported work is
`manual_only`; it is never hidden behind a generic subprocess helper.

## Local data profiles

Local profiles are data-only JSON used for application preferences. Imports
reject unknown fields, unsafe paths, symlinks, oversized files, unsupported
schemas, and invalid values. A profile never imports Python code and never
creates a host mutation outside the reviewed Action Center lifecycle.

## Verification

```bash
just test-file test_product_catalog
just check-drift
LOOFI_IPC_MODE=disabled QT_QPA_PLATFORM=offscreen just verify
```

See the [provider contract](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/PLUGIN_SDK.md)
and [architecture document](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/ARCHITECTURE.md).
