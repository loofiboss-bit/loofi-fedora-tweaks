# Architecture — v24.0.0 "Flow"

## Goal

Make existing capabilities easier to discover, understand, review, and finish
through one restrained KDE-native presentation system. Action Center clarity
is the highest product priority, built on shared navigation, header, state,
action, row, and feedback foundations.

## Protected contracts

- Keep exactly six standard destinations: `home`, `software_updates`,
  `system`, `network_security`, `desktop`, and `settings`.
- Keep all stable route IDs, redirects, section IDs, catalog identifiers,
  persisted schemas, lazy construction, and startup order.
- Keep UI presentation in `ui/`; keep selection policy, lifecycle state,
  persistence, package behavior, and troubleshooting composition in PyQt-free
  `core/` or `services/` owners.
- Keep `BaseTab` and `CommandRunner` for asynchronous GUI command flows.
- Keep Action Center as the sole confirmed host-mutation authority. Opening,
  selecting, browsing, filtering, reviewing, or navigating never executes.
- Keep explicit preflight, plan validation, confirmation, audit, rollback,
  verification, expiry, lease, interruption, and recovery boundaries.
- Keep `pkexec`, explicit timeouts, unpacked `PrivilegedCommand`,
  `SystemManager.get_package_manager()`, and separate Traditional/Atomic paths.

## Shared presentation architecture

The existing `ui/components/` package remains the only semantic widget layer.
V24 extends it by cohesive responsibility rather than creating another widget
system:

- `actions.py`: primary, secondary, quiet, destructive, and retry roles;
- `layout.py`: contextual page and section headers, bounded content, adaptive
  layouts;
- `feedback.py`: status badges, banners, loading/empty/error/success/disabled
  states, progress and technical disclosure;
- `settings.py`: aligned setting rows and local saved/changed/error/restart
  feedback;
- new focused row/summary helpers only where Applications, Troubleshooting, or
  Action Center share real repeated presentation.

Every semantic component exposes text plus accessible name/description, uses
theme palette roles rather than hard-coded status colours, supports keyboard
focus, and avoids fixed pixel geometry that clips under 100–200% scale.

`ui/icon_pack.py` owns one semantic mapping from actions/states to ordered Qt
theme names and the existing deterministic fallback assets. Callers request a
semantic role instead of repeating generic or unrelated icons.

## Shell and headers

The existing destination catalog remains authoritative. Presentation labels
are sanitized at their shell boundary so mnemonic markers never leak into the
visible destination or page header. Visual grouping is presentation-only and
does not introduce parent destinations, extra rows, route identifiers, or a
second navigation model.

The shell owns one contextual header for every realized route: title, concise
purpose, optional status, and at most one primary page action. Page content may
use section headers but must not duplicate competing page titles.

## Home and onboarding

PyQt-free Home composition continues to read saved bounded state only. A pure
deterministic selector chooses the next action using the existing safety-first
ordering. Integrated onboarding is a small versioned XDG preference record
with current step and dismissal state; it does not probe the host, gate the
application, navigate automatically, or execute an operation. Home cards only
emit stable existing route IDs.

## Applications and Updates

Applications keep the existing closed curated definitions and
`ApplicationOperationService`. Row presentation derives source, installed/
available/planned/unavailable state, progress, feedback, and one primary
review action from existing data. Native Discover remains an explicit handoff
for the broader catalog.

Updates keep existing package and firmware detection and the existing Action
Center handoff. UI lifecycle names are a presentation of current check,
availability, plan, operation, and terminal states; no new backend state
machine or automatic refresh is introduced.

## Troubleshooting

`TroubleshootingService` remains the only collection entry. The UI presents
three stable stages—Problem, Checks, Results—plus progressive details and
existing session/history actions. Profile selection and stage navigation are
inert. A worker begins only after the explicit Start action. Extracted modules
may render profile, evidence, session, or result views but may not compose
evidence or own lifecycle transitions.

## Action Center

The Action Center uses one desktop split view:

- the master area switches explicitly between Review queue and Catalog;
- the detail area shows the selected existing plan/run/definition evidence;
- plan preparation/review is separate from selection;
- a lifecycle action presenter maps existing plan/run states to at most one
  primary action and optional quiet navigation/details actions.

Review queue is the initial mode. Catalog browsing never implies approval.
Risk, affected scope, requirements/preflight, validation, rollback, privilege,
restart, unavailable reason, and verification are visible before Run Plan.
State names come from existing ActionPlan/ActionRun contracts; no parallel
lifecycle or alternate executor is allowed.

## Module decomposition

The touched 900+ line Action Center and Troubleshooting source modules are
split only along reusable presentation responsibilities. Compatibility
classes and public imports stay at their current paths. Extracted widgets are
substantial owners of layout/state rendering, not forwarding wrappers.

## Verification boundary

Automated qualification covers route identity, inert navigation/review,
semantic roles, keyboard focus, accessible names, long strings, RTL, high
contrast, and 100%, 125%, 140%, 150%, and 200% scale geometry with Qt
offscreen. Repository screenshots are the visual baseline. Real updated
screenshots are captured only if the environment supports authentic rendering.
Offscreen evidence never claims physical Wayland, audible Orca, manual
keyboard, fresh Atomic, or human contrast qualification.

The release requires the canonical tests, coverage, lint, typecheck,
architecture, drift, packaging, release documentation, version, and diff
gates before the exact-tag workflow may publish it. Public completion requires
independent readback of exact lineage, CI and CodeQL, release assets,
checksums, SBOM, provenance and attestations, COPR packages and signatures, a
clean disposable Fedora 44 installation, and the source-controlled wiki.
Physical Wayland, fresh Atomic, manual keyboard, and audible Orca evidence may
remain explicitly unverified and must never be inferred from automation.
