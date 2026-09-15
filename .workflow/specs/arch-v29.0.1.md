# Architecture — v29.0.1 "Utility"

Status: release implementation contract.

## Product boundary

The supported GUI presents Home, Install, Tune, Fix, and Update. Activity &
Recovery and Settings are secondary header routes. There is no background
service, web API, arbitrary shell execution, unattended scheduler, automatic
retry, rollback, or reboot.

The historical `v29.0.0` tag belongs to the earlier "Usability & Polish"
line. It remains immutable; `v29.0.1` is the unambiguous Utility Renovation
release identity.

## Authority

`ActionCenterOrchestrator` is the sole persistent mutation authority. Legacy
queue execution is removed; old schema-v4 plans and runs remain readable.
Every GUI operation uses the shared PyQt-free operation controller and its Qt
adapter for the same lifecycle:

```text
prepare → optional confirmation → execute → verify → recovery guidance
```

## Task catalog

`TaskDescriptor` is the product projection for a user task. It carries a
stable task ID, owning route, target variant and capability requirements,
risk and interaction policy, typed inputs, availability explanation,
verification summary, recovery guidance, and search terms. Stable action IDs
remain the execution and persistence identity.

Only tasks with a complete start point, parameters, preflight, verifier, and
terminal result are executable in the normal UI. Manual-only tasks are
instructions or native-settings handoffs.

## Change sets

Install multi-select and Tune profiles use the versioned
`loofi.action-bundle/v1` envelope with an immutable ordered member list and
per-member results. Application members continue independently after a
failure. Tune members execute in order and stop at the first unexpected
failure. A bundle never implies rollback, retry, or reboot.

## Journeys

- Install provides a curated, searchable, source-labelled application catalog
  with Flatpak-first GUI choices and capability-gated Fedora RPM choices.
- Tune provides editable Minimal, Recommended, and Power User profiles limited
  to implemented and verifiable operations.
- Fix starts from a symptom, presents findings, and offers one supported
  repair, instruction, or native-settings handoff.
- Update presents System, Flatpak, and Firmware as independent state-driven
  cards with exactly one primary action each.

## Compatibility

Persisted Action Center schema v4 remains readable. `changes` and
`maintenance:action-center` redirect to Activity & Recovery. The CLI keeps
`changes` as an alias for Activity list/detail while explicit legacy plan
application and verification verbs remain available for the v29 line.

## Qualification

The isolated deterministic gate, architecture and product validators,
packaging checks, RPM smoke test, release documentation, and public artifact
readback are release requirements. Physical Fedora, desktop, Polkit, reboot,
Atomic, keyboard, scaling, and Orca checks are reported as `unverified` when
not run and are never inferred from offscreen evidence.
