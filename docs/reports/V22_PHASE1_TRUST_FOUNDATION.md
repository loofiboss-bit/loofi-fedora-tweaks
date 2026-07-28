# V22 Phase 1 Trust Foundation

Date: 2026-07-28  
Baseline: `3c9ce62a14839f40dd1ac027cc43a83476f27571`  
Product version: `21.0.0 "Resolve"`  
Active target: `22.0.0 "Alignment"`

## Outcome

Phase 1 closes the five verified trust boundaries and the two optional RPM
runtime dependency gaps. COPR completion, support exports, Flatpak application
state, and application shutdown now fail closed through executable contracts.

## Security and correctness closure

### COPR publication

- Result artifacts remain diagnostic and cannot end polling.
- Only authoritative API status `succeeded` opens the repository gate.
- Poll timeout, terminal failure, repository-install failure, and installed
  version mismatch fail the workflow.
- `scripts/copr_release_gate.py` provides executable state decisions for
  running, failed, timed-out, install-unavailable, mismatched, and ready facts.

The original `running + visible artifacts + failed install` path no longer
reaches a success summary.

### Runtime packages and Flatpak state

- The API RPM requires `python3-python-multipart`.
- The daemon RPM requires `python3-gobject-base`.
- All delivered Flatpak application checks use direct
  `flatpak info <application-id>` vectors under the existing `shell=False`
  boundary.

### Bounded application shutdown

- Runtime resources expose inert `request_stop()` and `wait_for_stop(timeout)`
  hooks.
- All stop requests start in LIFO order and are collected for at most half the
  shared deadline; one hanging request cannot withhold later stop signals.
- Resource waits use the remaining absolute deadline.
- Request, wait, false-result, and timeout failures are recorded per resource.
- EventBus and MainWindow implement the two-phase contract while Qt-owned
  cleanup remains on the GUI thread.

Both a hanging request hook and a hanging wait hook return within the configured
budget in regression tests.

### Support evidence privacy

- Shared free-text redaction masks Bearer and Basic authorization headers.
- Token, password, secret, API-key, access-key, private-key, and credential
  values are masked with colon, equals, or whitespace separators.
- End-to-end journal export coverage proves the raw values do not reach the
  generated support bundle.

## Verification

- Full `just verify`: 6,875 passed, 61 skipped, 1,072 passed subtests,
  20 non-failing warnings, and 86.45 percent coverage.
- Lint, mypy, architecture, stabilization, release-document, workflow,
  packaging, JSON/YAML parsing, and diff checks pass.
- Runtime/EventBus/MainWindow focused lifecycle suites pass.
- COPR state-machine, Flatpak catalog, RPM dependency, and support-redaction
  regressions pass through their owning boundaries.
- Fedora 44 repository metadata exposes both newly required dependency package
  names.

No live GitHub/COPR job, clean RPM-container installation, or public release
was run. Those remain Phase 5/release evidence and cannot be inferred from
local workflow tests.

