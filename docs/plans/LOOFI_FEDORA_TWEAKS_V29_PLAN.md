# Loofi Fedora Tweaks v29.0.1 "Utility" — Utility Renovation

Status: release implementation complete on the v28.0.3 baseline. The
historical `v29.0.0` tag remains immutable; `v29.0.1` is the unambiguous
release identity for this renovation.

## Product direction

Loofi becomes a curated Fedora utility organised around four everyday jobs:

- **Install** — discover and install trusted applications with source-aware
  multi-select and per-item results.
- **Tune** — choose editable Minimal, Recommended, or Power User selections
  for verified Fedora, privacy, performance, and desktop options.
- **Fix** — start from a symptom, inspect bounded evidence, and apply one
  verified repair when the platform contract supports it.
- **Update** — inspect and update system packages, Flatpaks, and firmware
  independently with state-driven feedback.

Home remains the launchpad. Activity & Recovery is the secondary place for
work that needs user attention, reboot follow-up, verification, or recovery.
Settings remains a header route.

## Architectural decisions

`core/actions` remains the internal execution engine. The orchestrator is the
only persistent host-mutation path and keeps typed parameters, fresh preflight,
authorization, a mutation lease, independent verification, and fail-closed
platform handling.

The user-facing product is driven by a shared task descriptor containing a
stable task ID, plain-language goal, owning route, availability, target
variants, risk, interaction policy, parameter form, verification summary, and
recovery guidance. Action IDs remain stable for persisted state and CLI
compatibility.

App selections and Tune profiles use a versioned change-set envelope. Each
member is prepared and verified independently. App batches continue after an
individual item fails; ordered Tune profiles stop at the first unexpected
failure. No batch automatically retries, rolls back, or reboots.

The visible Changes/Action Center catalog is retired. Existing `changes` and
`maintenance:action-center` routes redirect to Activity detail while persisted
v4 plans and runs remain readable. Manual-only definitions become explicit
instructions or native-settings handoffs instead of disabled execution buttons.

## Navigation and compatibility

The visible shell exposes Home, Install, Tune, Fix, and Update. Each landing
page has no more than five task groups. Old route IDs remain compatibility
redirects for one major line and never instantiate the retired Action Center
screen. The CLI keeps `changes` as an alias for Activity history/detail while
explicit plan application and run verification remain supported during the
migration.

## Acceptance gates

- Golden paths complete inline: discovery → explanation → optional confirmation
  → execution → verification → recovery guidance.
- No active task is shown without a complete owning page, typed parameters,
  preflight, verifier, and truthful terminal state.
- Keyboard, 100–200% scaling, light/dark themes, KDE/GNOME, traditional Fedora,
  and supported Atomic paths are qualified before they are marketed.
- `LOOFI_IPC_MODE=disabled QT_QPA_PLATFORM=offscreen just verify`, architecture
  and product contracts, packaging, RPM smoke tests, documentation checks, and
  current-state visual evidence pass before the v29 release candidate.
- Physical, Polkit, reboot, Atomic, keyboard, and Orca evidence is recorded as
  verified or `unverified`; unverified environments are not advertised as
  supported.

The v29.0.1 release uses the repository's canonical tag-driven GitHub and COPR
workflow. Host installation and reboot are separate operations and are not
implied by publication.
