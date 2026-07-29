# Loofi Fedora Tweaks v23.0.0 "Compass"

## Canonical implementation plan

**Repository:** `loofiboss-bit/loofi-fedora-tweaks`  
**Reviewed branch:** `master`  
**Reviewed head:** `8c089f4f460a67099dbad02a8afdede98b6d7b7f`  
**Phase 0 baseline head:** `5bd323b6794c72bb17390149a4e07bff3e35bf35`
**Current public release:** v22.0.0 "Alignment"  
**Proposed release:** v23.0.0 "Compass"  
**Primary theme:** Guided troubleshooting and explainable support sessions  
**Plan date:** 2026-07-29

## 1. Decision

V23 should turn the existing System Check, Trusted Change Journal,
observability, release-readiness, and Action Center foundations into one
coherent troubleshooting journey.

The top priority is not another UI redesign or another collection of standalone
tweaks. The product already has mature safety, execution, history, navigation,
and release infrastructure. Its next major user-facing value is helping a user
answer:

1. What is wrong?
2. What evidence supports that conclusion?
3. What changed near the time the problem started?
4. What is the safest next step?
5. Did that step actually resolve the original problem?

Compass should answer those questions without claiming causality it cannot
prove, adding automatic repair, or creating a second execution authority.

## 2. Verified starting point

The reviewed repository currently has:

- v22.0.0 "Alignment" published from release commit
  `31dc3ac7af53367f2bd257336ad0282cadea5fe7`;
- 81 stable routes and 63 classified first-party Action Center definitions;
- 1,461 tracked files, 414 production Python files, and 319 test modules at the
  Phase 0 baseline;
- 6,916 locally passing tests, 61 expected skips, 1,079 passing subtests, and
  86.66 percent coverage in the Phase 0 verification;
- one-provider, probe-free Home startup with a final measured median of
  169.528 ms and 76,828 KiB RSS;
- no open GitHub issues or pull requests at review time;
- a completed safe execution boundary, System Check comparison model,
  source-owned Trusted Change Journal, and read-only loopback API.

The remaining product opportunity is composition. The application can inspect,
record, correlate, plan, execute, and verify, but those capabilities are still
spread across several user surfaces.

### Baseline inconsistencies to close before runtime work

- `ARCHITECTURE.md` still describes v21 as current and v22 as active.
- `docs/FEDORA_KDE_44_READINESS.md` still introduces the product as v15.
- Some architecture text refers to Support Bundle v11 even though the canonical
  writer is v12.
- V20 must remain historically `PUBLICATION BLOCKED`; its old post-publication
  tasks must not be silently marked complete.
- The historical annotated tag `v23.0.0` already exists and peels to
  `adc4cef116d147bd5b845f0ec98c3a1970b8b054` ("Architecture Hardening").
  Phase 0 must preserve it and record the naming collision; moving, deleting,
  replacing, or publishing a tag requires separate release authority.

These are Phase 0 authority fixes, not the V23 product theme.

## 3. Product outcome

Compass introduces one canonical **Troubleshoot** workflow under the existing
System destination. It reuses an existing diagnostics/troubleshooting route
selected during Phase 0 and must not add a seventh top-level destination.

The user selects a problem profile, explicitly starts a bounded read-only
session, reviews current findings and possibly related changes, then chooses
one safe next step:

- open an existing route;
- create one existing audited Action Center plan;
- follow truthful manual guidance;
- collect additional explicit evidence; or
- export a privacy-safe support case.

After a verified action, the user can explicitly rerun the compatible profile.
The follow-up result reports whether the original finding is resolved,
unchanged, worsened, or not comparable.

### User-visible success

- Troubleshooting starts from a real symptom instead of an internal subsystem.
- Each result shows source, collection time, freshness, applicability, and
  evidence quality.
- Recent changes are labelled **Possibly related**, never presented as proven
  causes.
- Partial evidence is visibly partial and can never produce an all-clear.
- Exactly one primary next step is presented for the selected finding.
- A support case can be exported without raw command output, secrets, personal
  paths, host identifiers, or command vectors.
- Traditional Fedora and Atomic Fedora receive different, truthful guidance
  where their package, boot, and recovery models differ.

## 4. Closed troubleshooting profiles

V23 should ship a small closed profile catalog rather than a free-form command
or plugin interface.

| Profile ID | User wording | Initial bounded evidence |
| --- | --- | --- |
| `system_slow` | System feels slow | resource trend, pressure, failed services, recent package/deployment changes |
| `updates_failed` | Updates failed | package-manager state, locks, repository health, pending deployment, related Action Center runs |
| `application_failed` | An application will not start | package/Flatpak presence, recent app changes, bounded journal metadata, no arbitrary process launch |
| `network_problem` | Network is not working correctly | NetworkManager state, DNS/connectivity metadata, recent connection changes, no network scan |
| `storage_pressure` | Storage is low or filling up | filesystem pressure, reclaim analysis, recent package/Flatpak activity |
| `boot_or_deployment` | Boot, kernel, or deployment problem | boot identity, failed units, pending reboot, kernel/deployment history, Atomic applicability |

Phase 0 must verify which existing collectors can serve each profile. A profile
must be reduced or marked unavailable when its required evidence cannot be
collected safely and deterministically.

## 5. Domain contract

### Troubleshooting session

Add a PyQt-free `core/troubleshooting/` domain with immutable, versioned
contracts.

Each session contains:

- schema version and stable opaque session ID;
- closed profile ID and profile version;
- Traditional or Atomic host variant;
- state: `queued`, `running`, `completed`, `partial`, `cancelled`, or `failed`;
- started and completed timestamps;
- completed, unavailable, timed-out, and failed evidence sources;
- bounded structured findings;
- bounded possibly-related change references;
- compatibility metadata for follow-up comparison;
- no command vector, callback, renderer, token, secret, or raw process output.

Sessions are created only after explicit user or CLI activation. Constructing
Home, navigation, search, the API, or the Troubleshoot page must not start a
session.

### Finding

Every finding contains:

- stable finding type and deterministic privacy-safe fingerprint;
- severity and category;
- plain-language title, summary, and evidence explanation;
- source, timestamp, freshness, and affected resource identifiers;
- evidence-quality state: `confirmed`, `supported`, `limited`, or `unknown`;
- Traditional/Atomic applicability;
- exactly one next-step kind:
  - existing Action Center action ID plus closed typed parameters;
  - navigation-only route plus inert preselection metadata;
  - explicit additional read-only collection;
  - manual guidance with a reason code; or
  - no safe next step.

Evidence quality describes the available evidence. It must not be exposed as a
statistical probability or causal confidence score.

### Related-change contract

Correlation reuses source-owned Trusted Change Journal records.

- Match only by bounded time window and normalized affected resources.
- Keep the V20 wording **Possibly related**.
- Show why the item was associated: time proximity, shared resource, or both.
- Never store or infer a recovery command.
- Never convert correlation into an automatic Action Center plan.
- Missing journal sources remain unavailable, not empty.

### Follow-up comparison

Extend the existing System Check comparison principles:

- compare only the same profile version and Fedora variant;
- require later completed evidence from the relevant source;
- classify original findings as `resolved`, `unchanged`, `worsened`, or
  `not_comparable`;
- keep Action Center `verified` separate from troubleshooting `resolved`;
- do not infer improvement from arbitrary free-form text;
- do not rewrite historical sessions during comparison.

### Persistence

- Do not create another SQLite database.
- Prefer composing existing saved System Check, observability, journal, plan,
  and run records.
- Persist a bounded session JSON only when needed for history, comparison, or
  an explicit support export.
- Use the existing XDG inventory, atomic write, permission, backup, schema, and
  future-version read-only contracts.
- Unknown future session schemas are read-only and never rewritten.

## 6. Protected contracts

V23 must preserve:

- all 81 existing stable route IDs, aliases, favorites, direct links, saved
  navigation, and lazy loading;
- the six-destination shell and one canonical Home;
- Action Center schema v4 and its one-action-per-plan rule;
- fresh preflight, explicit confirmation, one mutation lease, independent
  verification, and no automatic reboot, retry, rollback, resume, or chaining;
- System Check and Trusted Change Journal source ownership;
- existing observability stores and historical support-bundle readers;
- CLI JSON envelope compatibility, daemon and D-Bus behavior, and the
  authenticated loopback-only read-only API;
- Traditional/Atomic policy separation;
- cold startup with one realized Home provider and no subprocess probes,
  active timers, or running QThreads;
- fixed, non-privileged V22 native handoffs;
- V20's historical `PUBLICATION BLOCKED` status.

## 7. Explicit non-goals

Do not include:

- AI-generated diagnoses, cloud analysis, telemetry, or account requirements;
- automatic monitoring, background polling, or unsolicited checks;
- Fix All, bulk plans, chained actions, or automatic confirmation;
- a mutating HTTP API;
- arbitrary shell commands, user-authored probes, or executable extensions;
- another global navigation redesign or theme rewrite;
- a seventh top-level destination;
- a new authoritative journal or metrics database;
- external plugin execution or Marketplace restoration;
- a physical Specialist Tools RPM split;
- automatic rollback, reboot, retry, or resume;
- a Fedora 45 stable-support claim before official final availability and
  fresh physical Traditional plus Kinoite qualification;
- reopening the completed v16-v22 catalog, shell, native-handoff, lifecycle,
  COPR, or redaction projects without a failing baseline gate.

## 8. Implementation phases

### Phase 0 — Authority, baseline, and scope lock

**Goal:** establish the exact v22 state and prevent documentation or contract
drift before runtime work.

Tasks:

- create the canonical V23 plan, architecture spec, task contract, and active
  race lock;
- record exact branch, commit, tag, working tree, release, CI, COPR, and
  package state;
- correct stale current-version, active-target, Fedora-readiness, and support
  bundle documentation;
- inventory all diagnostics, troubleshooting, System Check, Activity &
  Recovery, Home, Action Center, CLI, API, and support-export routes;
- select the existing route that will become the canonical Troubleshoot
  surface;
- inventory all collectors, stores, schemas, command boundaries, timers,
  workers, and source-specific timeouts;
- record full tests, coverage, lint, mypy, architecture, startup/RSS,
  System Check timing, route projection, and support-redaction baselines;
- capture deterministic wide and compact screenshots of the current relevant
  surfaces;
- keep product metadata at v22.0.0 and make no runtime change.

Acceptance:

- authority documents agree on v22 current and v23 active;
- all existing contracts and validators pass unchanged;
- no route, state, UI, version, package, tag, or remote mutation occurs.

### Phase 1 — Troubleshooting domain and profile catalog

**Goal:** define the safe, PyQt-free session model before adding UI or
interfaces.

Likely ownership:

- `core/troubleshooting/`
- existing collector/service adapters
- XDG/state schema inventory
- unit and architecture tests

Tasks:

- implement immutable session, profile, source-result, finding, next-step, and
  comparison contracts;
- define the six closed profiles and exact collector budgets;
- validate profile IDs, typed parameters, resource identifiers, and limits;
- reject commands, callbacks, renderers, unknown actions, unbounded text, and
  future writable schemas;
- implement cancellation and per-source timeout semantics;
- persist only bounded privacy-safe session data through existing atomic state
  infrastructure;
- keep domain imports free of PyQt.

Acceptance:

- complete state matrices cover success, partial, unavailable, timeout,
  cancellation, malformed data, and future-schema cases;
- importing the domain performs no probe, write, timer, thread, or UI import;
- no session can contain execution authority.

### Phase 2 — Evidence composition and conservative correlation

**Goal:** assemble existing trusted evidence into a useful answer without
duplicating source ownership.

Likely integrations:

- `core/system_check/`
- `core/change_journal/`
- `core/observability/`
- `core/diagnostics/release_readiness.py`
- Action Center read-only plan/run stores

Tasks:

- create read-only adapters for the exact evidence required by each profile;
- compose current findings, trends, recent source-owned changes, and linked
  plan/run facts;
- implement time/resource matching with explicit reason codes;
- preserve unavailable, empty, partial, stale, and failed source states;
- add compatible before/after comparison;
- ensure Traditional and Atomic evidence cannot be mixed;
- benchmark each profile and enforce per-source and total budgets.

Acceptance:

- correlation is deterministic and always labelled **Possibly related**;
- a partial source cannot produce an all-clear;
- no adapter writes, migrates, confirms, executes, verifies, or mutates;
- no new durable database is introduced.

### Phase 3 — Canonical Troubleshoot experience

**Goal:** make the end-to-end workflow understandable to a normal Fedora user.

Likely ownership:

- one existing System diagnostics/troubleshooting route;
- a new presentation widget under `ui/`;
- shared v16-v22 components and semantic design tokens;
- `core/home/`, navigation search, and inert route preselection.

Journey:

1. Choose a problem.
2. Review what will be checked.
3. Start the explicit read-only session.
4. Review current findings and possibly related changes.
5. Choose one next safe step.
6. Return after verification and check again.

Tasks:

- use one page scaffold and one local view switcher;
- show one primary action for the current state;
- keep technical evidence collapsed but keyboard reachable;
- show freshness, source readiness, Fedora variant, and partial-result warnings;
- support cancellation without discarding the previous completed session;
- link Home and global search to the canonical surface without adding probes;
- use only existing Action Center handoff contracts;
- provide truthful empty, unavailable, cancelled, partial, failed, and
  not-comparable states;
- use `self.tr()` for all user-visible strings.

Acceptance:

- no duplicate Troubleshoot page, wizard, or history surface exists;
- route count and all current route identities remain unchanged;
- keyboard, visible focus, screen reader, 900/1180/1366 DIP geometry, 100-200
  percent scale, dark/light/system/high-contrast, RTL, and reduced-motion
  matrices pass;
- no widget directly owns subprocess or domain policy.

### Phase 4 — CLI, read-only API, and support case

**Goal:** provide scriptable inspection and a bounded handoff for support
without expanding remote authority.

CLI contract:

```text
loofi troubleshoot profiles
loofi troubleshoot run PROFILE_ID
loofi troubleshoot show SESSION_ID
loofi troubleshoot latest
loofi troubleshoot compare SESSION_ID FOLLOWUP_ID
loofi troubleshoot export SESSION_ID
loofi --json troubleshoot latest
```

Tasks:

- keep CLI parsing and service calls outside UI modules;
- preserve the stable JSON envelope and add a versioned payload;
- expose only authenticated read-only API retrieval for the latest or a known
  bounded session;
- do not add an HTTP endpoint that starts collection or creates a plan;
- advance the canonical Support Bundle from v12 to v13;
- include at most one selected session, 50 findings, 25 related journal
  references, 25 linked plan/run records, and one comparison;
- exclude raw stdout/stderr, commands, secrets, tokens, personal paths,
  hostnames, emails, IP/MAC identifiers, and unbounded evidence;
- retain v2-v12 support-bundle readers unchanged.

Acceptance:

- CLI collection is explicit and cancellable;
- API construction and GET requests never collect or mutate;
- recursive redaction tests prove seeded sensitive values are absent from every
  output form;
- unknown future support/session schemas fail closed.

### Phase 5 — Platform, performance, and security qualification

**Goal:** prove the new workflow is safe on the actual supported platforms.

Tasks:

- run focused and full repository verification;
- validate architecture, product catalog, route equality, release docs,
  packaging, generated adapters, statistics, and version alignment;
- run Bandit, pip-audit, CodeQL, malicious-input, timeout, and redaction tests;
- enforce Home startup within the Phase 0 × 1.10 median/RSS ceilings;
- enforce one Home provider and zero cold-start probes, timers, and QThreads;
- set and verify explicit total budgets for all six troubleshooting profiles;
- perform physical Fedora 44 KDE Wayland, keyboard, Orca, and AT-SPI journeys;
- perform fresh Traditional and Kinoite/Atomic profile qualification because
  the new evidence composition is variant-aware;
- test RPM, optional API/daemon RPMs, Flatpak, and source installation;
- build checksums, SBOM, provenance, and local candidate evidence.

Acceptance:

- `just verify` and all release validators pass;
- global coverage remains at least 86 percent without excluding new domain
  code;
- every new state and security boundary has direct tests;
- no physical or release claim is inferred from offscreen, mock, container, or
  carried-forward evidence.

### Phase 6 — Release readiness and separately authorized publication

**Goal:** prepare an exact release candidate while keeping external actions
separate.

Tasks:

- synchronize version metadata to v23.0.0 "Compass" only after Phases 0-5 pass;
- generate release notes, changelog, user/admin guides, screenshots, and
  troubleshooting documentation;
- rebuild all artifacts from the exact candidate commit;
- verify checksum, SBOM, provenance, package metadata, and upgrade/install
  lifecycle locally;
- record remaining physical, Fedora 45, signing, GitHub, COPR, wiki, and public
  readback gates truthfully.

External commit, push, tag, release, COPR, host installation, and documentation
publication remain separately authorized operations.

## 9. Quality gates

### Repository

- `just verify`
- `just validate-release`
- `just check-packaging`
- `just check-drift`
- `just stats-check`
- product and architecture validators
- version and race-lock alignment
- `git diff --check`

### Safety

- no `sudo`;
- no `shell=True`;
- list-based allowlisted commands only;
- timeout on every subprocess;
- no command-bearing session, finding, journal link, API response, or support
  export;
- no automatic confirmation, execution, reboot, rollback, retry, or resume;
- one existing Action Center plan per supported finding;
- malicious identifiers and oversized/unbounded inputs fail closed.

### Performance

- Home median and RSS at or below Phase 0 × 1.10;
- one realized Home provider;
- zero cold-start subprocess probes, timers, or QThreads;
- explicit per-source and per-profile collection budgets;
- cancellation returns within the shared deadline;
- no repeated probing when composing already-saved evidence.

### Compatibility

- exact ordered projection of all 81 existing routes;
- aliases, favorites, saved routes, direct links, and search remain valid;
- v22 state and older supported schemas remain readable;
- v2-v12 support bundles remain importable;
- CLI/API/daemon/D-Bus compatibility tests pass;
- Traditional and Atomic results never compare across variants.

## 10. Commit boundaries

Recommended checkpoints:

```text
docs(v23): lock Compass authority and baseline
feat(troubleshooting): add safe session and profile contracts
feat(troubleshooting): compose evidence and related changes
feat(ui): add canonical guided troubleshooting journey
feat(interfaces): add troubleshooting CLI and support bundle v13
test(v23): qualify Compass platform and release gates
chore(release): prepare v23.0.0 Compass
```

Do not combine the version bump or release-state changes with an earlier
implementation phase.

## 11. Codex execution order

1. Start with Phase 0 only.
2. Read `AGENTS.md`, `ARCHITECTURE.md`, `ROADMAP.md`, the V22 plan and reports,
   and the V23 plan before editing.
3. Inspect `.workflow/specs/.race-lock.json` before release-scoped work.
4. Compare every proposed new surface against the current catalog and
   documentation before creating files.
5. Implement one phase at a time and run focused tests before the full gate.
6. Stop when a physical-platform, publication, credential, signature, or
   external-authorization gate is reached.
7. Do not commit, push, tag, publish, install on the host, or modify GitHub/COPR
   unless separately requested.

## 12. Definition of done

V23 is complete only when a Fedora user can explicitly choose a real problem,
run a bounded read-only troubleshooting session, understand the evidence and
possibly related changes, open one safe next step, and verify the follow-up
result—while every existing route, safety boundary, stored record, startup
contract, platform distinction, and public interface remains intact.
