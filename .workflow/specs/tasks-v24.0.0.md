# Tasks — v24.0.0 "Flow"

## Contract

V24 converges the existing product around a shared semantic presentation
system. It preserves the six standard destinations, all route identifiers,
lazy loading, explicit Action Center execution, validation, audit logging,
Traditional/Atomic separation, and every supported feature.

- [x] ID: T1 | Requirements: REQ-001, REQ-002 | Files:
  `loofi-fedora-tweaks/ui/components/`, `loofi-fedora-tweaks/ui/icon_pack.py`,
  `loofi-fedora-tweaks/ui/navigation/`, shell presentation and tests | Dep:
  none | Description: Consolidate contextual headers, semantic action roles,
  section/state/search/summary/row primitives, icon roles, and navigation
  states without changing destination or route contracts. Acceptance: the six
  standard destinations and lazy wiring remain byte-for-byte identifiable;
  visible labels contain no mnemonic artifacts; affected controls expose
  names, focus, disabled, and notification state; 100%, 125%, 140%, 150%, and
  200% scale contracts have deterministic coverage. Tests:
  `tests/test_v24_flow_foundation.py`, existing navigation/accessibility tests.

- [x] ID: T2 | Requirements: REQ-003 | Files:
  `loofi-fedora-tweaks/core/home/`, Home UI, onboarding state and tests | Dep:
  T1 | Description: Make Home the task-oriented control point with saved
  status, deterministic next action, common navigation-only tasks, outstanding
  review information, and integrated resumable/dismissible first-run guidance.
  Acceptance: Home construction performs no system probe or mutation;
  deterministic ordering and onboarding persistence are PyQt-free and tested;
  experienced users are never blocked. Tests: `tests/test_v24_flow_home.py`,
  `tests/test_home_service.py`, `tests/test_home_ui.py`.

- [x] ID: T3 | Requirements: REQ-004 | Files: Applications and Updates UI,
  shared software presentation helpers, application operation service tests |
  Dep: T1 | Description: Clarify Discover versus Loofi, unify search/filter and
  application rows, expose source/status and one state-appropriate action, and
  distinguish update check, availability, review, running, terminal, and error
  states. Acceptance: no provider or package abstraction is added; explicit
  review remains mandatory; Traditional and Atomic paths remain distinct.
  Tests: `tests/test_v24_flow_software.py`, `tests/test_software_tab.py`,
  `tests/test_maintenance_updates_regression.py`,
  `tests/test_application_operations.py`.

- [x] ID: T4 | Requirements: REQ-005 | Files:
  `loofi-fedora-tweaks/ui/troubleshoot_widget.py`, cohesive extracted
  presentation module(s), troubleshooting service/session tests | Dep: T1 |
  Description: Present Troubleshooting as Problem → Checks → Results with an
  explicit safe start, progressive technical detail, and consistent terminal
  states while retaining history, compare, show, and export. Acceptance: page
  construction, problem selection, and result review collect nothing; all
  collection delegates to `TroubleshootingService`; existing profile budgets
  and session schemas remain unchanged. Tests:
  `tests/test_v24_flow_troubleshooting.py`,
  `tests/test_troubleshoot_widget.py`, `tests/test_troubleshooting_service.py`.

- [x] ID: T5 | Requirements: REQ-006 | Files: Action Center UI, cohesive
  extracted presentation module(s), Action Center regression tests | Dep: T1 |
  Description: Implement a desktop master-detail review queue with a separate
  catalog mode, visible selected-item evidence, explicit plan preparation and
  review, and one primary lifecycle action. Acceptance: browsing, filtering,
  selection, details, and review never confirm, apply, or verify; risk, scope,
  requirements, validation, rollback, and unavailable reasons are visible
  before Run Plan; UI names derive from existing plan/run states. Tests:
  `tests/test_v24_flow_action_center.py`, existing Action Center boundary and
  lifecycle suites.

- [x] ID: T6 | Requirements: REQ-007 | Files: System, Network, Settings,
  `maintenance_action_center.py`, `troubleshoot_widget.py`, and cohesive
  extracted UI modules | Dep: T1,T4,T5 | Description: Apply shared headers,
  sections, states, feedback, and setting rows to supporting high-traffic
  surfaces and split touched 900+ line modules by real presentation
  responsibility. Acceptance: changed/saved/error/restart-required settings
  feedback is explicit; risky detail is disclosed; large touched modules have
  materially lower complexity; public imports, routes, services, and lazy
  behavior remain compatible. Tests: `tests/test_v24_flow_supporting.py`,
  settings/network/system tests and architecture validator.

- [x] ID: T7 | Requirements: REQ-008 | Files: active documentation, release
  notes, workflow evidence, version metadata, screenshot manifests and
  qualification tests | Dep: T1,T2,T3,T4,T5,T6 | Description: Qualify the
  complete local V24 candidate, document current behavior, synchronize version
  metadata with `scripts/bump_version.py`, and prepare release artifacts without
  publication. Acceptance: focused tests, full tests, 86% coverage, lint,
  mypy, architecture, drift, packaging, release-doc, scale, accessibility and
  diff gates pass or retain exact honest limitations; version files agree on
  24.0.0 "Flow". Tests: `just test`, `just test-coverage`, `just lint`,
  `just typecheck`, `just check-drift`, `just check-packaging`,
  `just validate-release`, `just verify`.

- [x] ID: T8 | Requirements: REQ-009 | Files: release metadata, changelog,
  documentation, packaging, workflow contracts, and historical tag lineage |
  Dep: T7 | Description: Prepare the exact v24.0.0 release tree for the
  canonical tag-driven publication workflow and preserve the earlier
  "Power Features" tag target under an explicit legacy tag. Acceptance:
  publish-ready documentation gates pass; version metadata agrees on 24.0.0
  "Flow"; the historical target remains independently addressable; no safety
  or physical qualification result is inferred. Tests:
  `scripts/check_release_docs.py --require-publish-ready-tasks`,
  `scripts/bump_version.py --check`, `just check-drift`, `git diff --check`.

- [x] [post-publish] ID: T9 | Requirements: REQ-010 | Files: GitHub release,
  CI, CodeQL, COPR, Fedora 44 disposable install evidence, public wiki,
  roadmap, race lock, and publication report | Dep: T8 | Description: Publish
  and independently verify exact v24.0.0 lineage, release assets, checksums,
  SBOM, provenance and attestations, terminal COPR packages and signatures,
  a clean disposable Fedora 44 installation, and public documentation; then
  close the release state. Physical Wayland, fresh Atomic, manual keyboard,
  and audible Orca gates may remain explicitly unverified.

## Requirement traceability

| Requirement | Tasks | Primary verification |
| --- | --- | --- |
| REQ-001 | T1 | shell labels, route identity, sidebar states, scale matrix |
| REQ-002 | T1 | semantic primitive behavior, icons, accessibility |
| REQ-003 | T2 | next-action ordering, onboarding persistence, inert task navigation |
| REQ-004 | T3 | application rows, update lifecycle, Traditional/Atomic paths |
| REQ-005 | T4 | guided states, explicit start, service delegation |
| REQ-006 | T5 | review/catalog separation, evidence, explicit Run Plan regression |
| REQ-007 | T6 | supporting surfaces, setting feedback, module budgets |
| REQ-008 | T7 | full deterministic, packaging, docs, scale and accessibility gates |
| REQ-009 | T8 | publish-ready contracts, exact metadata, preserved historical lineage |
| REQ-010 | T9 | exact-tag CI, public artifacts, COPR, clean install, wiki readback |

## Non-goals

No QML/Kirigami rewrite, route or standard destination, marketplace, provider,
remote/cloud dependency, automatic repair, unattended execution, daemon/API
authority, package abstraction, hidden background change, runtime dependency,
or unsupported feature removal is permitted. Publication must not bypass
validation, safety, lineage, checksum, signature, or independent-readback
requirements. No physical or manual result may be inferred from automation,
and no host package installation or desktop configuration change is required.
