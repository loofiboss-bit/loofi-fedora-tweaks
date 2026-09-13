# Architecture — v26.0.3 "Everyday"

## Update inspection

`services/software/update_overview.py` owns immutable source results and explicit
read-only inspection. Its constructor and saved-state load do not run probes.
Each source retains checked time, status, candidates and known restart impact;
errors and freshness are separate from candidate count. Persist bounded snapshots
through existing XDG paths, advisory locking and atomic JSON writes. Recheck the
schema inside the write lock; preserve unknown future documents.

`ui/update_overview.py` owns the Qt worker and source presentation. The check
button is single-flight. Page destruction does not destroy its running worker;
late hidden-page results do not update the page. Returning reads saved state.
Source review buttons retain their existing closed Action Center handoff.

## Follow-up

Home composes a bounded list of persisted runs. Navigation carries the run ID
through the existing maintenance route and never creates a replacement plan.
Check result invokes the existing orchestrator verifier asynchronously. A reboot
pending outcome is informational/warning, never completed-success green.

## Interfaces and safety

No public API/CLI change, new route, database, dependency or privilege authority.
Existing documented plan/run schemas remain compatible. Services remain PyQt-free;
widgets contain presentation only. Fresh preflight, leases, confirmation and
independent verification remain mandatory at the existing execution boundary.
