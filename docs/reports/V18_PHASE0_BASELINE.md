# v18 Phase 0 Baseline and Scope Lock

Date: 2026-07-22  
Baseline: `e7c7c07c7442a679168613a01b41fc8c55eab90b`

## Release baseline

- v17.0.0 is released and independently verified; the working tree was clean
  and `master` matched `origin/master` at Phase 0 start.
- Full tests: 7,683 passed and 68 skipped on the local validation host.
- Coverage: 86.19 percent. Lint, mypy, stats, adapter drift, and release-doc
  checks passed before v18 changes.
- Runtime inventory: 374 Python modules, 303 test files, 80 stable routes, 28
  built-in plugin specs, seven destinations, and 61 destination sections.
- Startup contract: one Home plugin and zero subprocess probes, active hidden
  timers, or running worker threads. A fresh v18 measurement is required before
  the release gate is evaluated.

## Architecture baseline

- The five largest production hotspots include `cli/main.py`,
  `ui/main_window.py`, `ui/maintenance_tab.py`, `ui/community_tab.py`, and
  `core/diagnostics/release_readiness.py`.
- Product identity is duplicated across plugin specs, routes, placements, and sections.
- Specialist packaging remains unsafe: specialist-exclusive modules are still
  reachable from CLI, API, and daemon closures. A physical extras split is not
  a v18 deliverable.

## Mutation and security baseline

- The v17 gate covers five canonical workflows, but direct host writers remain
  in maintenance, security, software, network, hardware, backup/recovery, and
  multiple Advanced tools.
- External Python plugins use an advisory in-process sandbox that is not a
  security boundary. The configured CDN did not resolve and the GitHub fallback
  repository returned not found during Phase 0 readback.
- Gist credentials are stored in a mode-0600 plaintext file, while Web API JWT
  material is stored through the general configuration manager.
- The Web API is read-only after token issuance but accepted arbitrary host
  values from `LOOFI_API_HOST`.

## Documentation and quality baseline

- `.project-stats.json` reported zero tests, 80 percent coverage, and an active
  completed v17 pipeline because the stats collector used stale fallbacks and
  did not compare the committed JSON file.
- `SECURITY.md` described unsupported versions and removed API mutation routes;
  `CONTRIBUTING.md` described obsolete layer ownership and an 80 percent gate.
- `AGENTS.md` linked two instruction files that do not exist.

Phase 0 changes authority and evidence only. Product metadata remains 17.0.0
until all v18 release-candidate gates pass and a version bump is authorized.
