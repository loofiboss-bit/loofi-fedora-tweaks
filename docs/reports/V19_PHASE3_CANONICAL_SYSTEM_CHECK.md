# v19 Phase 3 — Canonical System Check

**Status:** Complete  
**Date:** 2026-07-24  
**Scope:** One read-only System Check page and compatibility migration

## Outcome

Standard mode now exposes one System Check section with Overview, Current
findings, and History. The History view presents saved JSON snapshots,
before/after finding counts, and collapsed summaries from the existing SQLite
metric timeline. No third health store, data rewrite, automatic collection, or
second Record Snapshot action was added.

The page explicitly distinguishes:

- a finding produced by a completed System Check;
- a sampled metric used only as supporting history;
- an Action Center run, which retains its separate review, execution, and
  verification boundary.

## Compatibility

| Contract | Phase 3 result |
| --- | --- |
| `health` | Preserved; opens the canonical System Check Overview |
| `maintenance:health-timeline` | Preserved; opens History in the same plugin |
| `Health`, `System Health`, `Health Timeline`, `My Fedora Today`, `Lighthouse` | Preserved aliases |
| Home and diagnostics deep links | Preserved as independent routes |
| Saved `health` and `maintenance:health-timeline` routes | Preserved without rewriting either ID |
| JSON health snapshots | Read in place through `HealthTimelineStore` |
| SQLite health metrics | Opened read-only when present; a missing database is not created |
| Snapshot and metric exports | Existing store and `health-history` implementations retained |
| `health snapshot`, `health timeline`, `health-history`, `maintenance today` | Existing CLI contracts retained |
| Standard destinations | Remains exactly six |
| Product routes | Remains exactly 80 |

`ui.health_timeline_tab.HealthTimelineTab` remains an import-compatible class
name backed by the canonical page. The old observability-history subtab and its
Record Snapshot action were removed from the Action Center UI module.

## New canonical CLI

- `loofi health check`
- `loofi health findings`
- `loofi health history`
- `loofi --json health check|findings|history`

Machine-readable output uses schema ID `loofi.system-check`, schema version 1,
and a command-specific `data` object. Human-readable text is not emitted in
JSON mode. Store failures are represented by bounded reason codes rather than
raw local paths or payloads.

## Trust and migration review

- The page and presentation service are read-only.
- The SQLite adapter uses URI `mode=ro` and does not initialize the metric
  schema.
- No state schema or migration was introduced.
- No snapshot, metric, route, alias, export, plan, run, or history record was
  deleted.
- System Check findings still carry no command vectors or executable
  callbacks.
- Action Center remains the only Review/Plan/Run/Verify/History execution
  authority; Phase 3 does not alter its schema-v3 digest, parameters,
  confirmation, preflight, lease, or verification behavior.
- Traditional and Atomic route availability remains unchanged.
- Home cold startup behavior is untouched by this phase.

## Verification

All Phase 3 checks passed:

```text
just test-file test_system_check_ui                 4 passed
just test-file test_navigation_compatibility       4 passed
just test-file test_cli_system_check               5 passed, 5 subtests
just test-file test_health_timeline                20 passed
just test-file test_v15_routes                     1 passed, 6 subtests
PYTHONPATH=loofi-fedora-tweaks python scripts/validate_product_contract.py
                                                    OK, 80 routes
just lint                                           passed
just typecheck                                      passed
```

Affected compatibility suites also passed:

```text
just test-file test_navigation_destinations        17 passed, 174 subtests
just test-file test_maintenance_tab                116 passed, 21 skipped
just test-file test_ui_tab_smoke                    53 passed
just test-file test_v16_phase4_system_routes       5 passed
just test-file test_cli_health                     28 passed
PYTHONPATH=loofi-fedora-tweaks python scripts/validate_architecture.py
                                                    passed
PYTHONPATH=loofi-fedora-tweaks python scripts/validate_v18_architecture.py
                                                    passed
PYTHONPATH=loofi-fedora-tweaks python scripts/validate_v18_haven.py
                                                    passed
```

The 21 skipped Maintenance tests are pre-existing conditional legacy branches;
the non-skipped Action Center trust-boundary tests passed.

## Remaining risk and deferred work

- Phase 3 verifies the page offscreen and with deterministic fixture stores; a
  real KDE accessibility and screenshot matrix remains Phase 6 work.
- Phase 4 owns the reviewed Action Center schema-v3-to-v4 decision required
  before persisting finding handoff context. Phase 3 stores no such context.
- Finding resolution comparison, support-bundle evidence, API parity, and final
  platform certification remain Phase 5 and Phase 6 work.

## Proposed checkpoint

```text
feat(ui): consolidate system checks and health history
```
