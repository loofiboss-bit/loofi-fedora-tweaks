# Architecture — v28.0.1 "Ease"

Status: local implementation candidate; the historical v28.0.0 workflow-reset
record remains unchanged and v27.0.1 remains the current public release.

## Product boundary

Ease refines the existing five-destination Fedora Maintenance Core. It does
not add a route, daemon, web API, specialist subsystem, unattended scheduler,
automatic retry, automatic rollback, automatic reboot, new runtime dependency,
or second mutation authority. GUI and CLI continue to use the existing
English product surface.

## Platform policy

`core/fedora_release_policy.py` is the single release-support policy. Fedora
43 and 44 are supported stable releases, Fedora 45 is preview, and all other
values are unknown. `PlatformProfile.support_status` is consumed by onboarding,
doctor, navigation, update inspection, and Action Center eligibility.

`PlatformProfile.deployment_backend` is the single backend authority:

| Backend | Read-only update inspection | Persistent update/recovery actions |
| --- | --- | --- |
| `dnf5` | DNF or the detected compatible DNF executable | Action Center when capability and verification are known |
| `rpm_ostree` | `rpm-ostree upgrade --preview` | Action Center with deployment/reboot evidence |
| `bootc` | Explicit manual guidance only | Unavailable until a separately qualified capability exists |
| `unknown` | Unavailable with an identification next step | Unavailable; no traditional fallback |

No caller may infer a backend from an atomic boolean when the typed profile is
available. Legacy injected runtimes are retained only as an in-process test
compatibility adapter and do not define production detection.

## Update overview contract

`services/software/update_overview.py` owns the read-only source contract.
System, Flatpak, and firmware results are independent typed records. A real
profile runtime checks at most three sources concurrently; each completed
source is published through a callback and persisted atomically. Cancellation
is cooperative and never creates a success result.

The schema is version 2. v1 observations remain readable but stale until a
new backend-aware check. A failed, unsupported, missing-tool, or cancelled
probe cannot replace a previous candidate list with an empty success. The
current failure is shown alongside the retained observation. The UI exposes
one explicit check button, per-source retry, cancellation, and a direct
`Review <source> updates` action only for a fresh supported result.

## Change Journal and history

`utils/history.py` keeps the existing typed, inert v2 history format under the
XDG state path. Missing history is an empty initial state. Corrupt, unreadable,
or future-schema history is unavailable; a list with valid and invalid entries
returns the valid entries with `partial` status. It never reconstructs or
executes legacy command vectors.

`core/change_journal` composes source-owned events without a third durable
store. The service bounds pages, retains per-source availability, isolates a
broken source from healthy sources, and returns an opaque `next_cursor`. The
Activity UI and `activity list --cursor` use pages of 25; selection is retained
when a page is appended.

## Search and Changes

`core/actions/catalog.py` remains the executable action authority. Global action
search projects non-manual entries from that catalog and adds only bounded
task-language aliases such as `free disk space`, `updates`, and `slow system`.
The search matcher is order-independent and routes to existing maintenance or
review destinations.

Changes remains the only persistent mutation authority. Its presentation shows
plain-language scope, privilege, restart, recovery, checked result, and next
step facts before technical detail. Unknown release/backend and bootc mutation
paths fail closed; manual guidance never masquerades as a completed action.

## Testing and qualification

The shared pytest configuration redirects HOME and all XDG roots to a temporary
session directory. System commands and host probes are mocked in product tests.
The deterministic full suite is the first local gate, followed by lint,
typecheck, architecture, product-contract, packaging, and coverage checks.

Physical KDE/GNOME, rpm-ostree, Polkit, reboot, Orca, keyboard, theme, scale,
small-screen, benchmark, and user-session evidence remains separate. Offscreen
tests do not prove physical qualification. Release publication and external
readback require a later explicit authorization.
