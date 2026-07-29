# V23 Phase 4 CLI, Read-only API, and Support Case

Date: 2026-07-29  
Active target: `v23.0.0 "Compass"`  
Product metadata: `v22.0.0 "Alignment"`  
Scope: local Phase 4 implementation only

## Outcome

Phase 4 exposes the retained Compass troubleshooting model through one
versioned CLI family, two authenticated retrieval-only API endpoints, and one
explicitly selected Support Bundle v13 case. It adds no route, database, HTTP
collection, plan creation, execution authority, product-version change, host
installation, tag, commit, or remote modification.

## CLI contract

The CLI now supports:

```text
loofi troubleshoot profiles
loofi troubleshoot run PROFILE_ID
loofi troubleshoot show SESSION_ID
loofi troubleshoot latest
loofi troubleshoot compare SESSION_ID FOLLOWUP_ID
loofi troubleshoot export SESSION_ID
loofi --json troubleshoot latest
```

Every JSON response uses schema ID `loofi.troubleshooting`, schema version 1,
the requested command, and a `data` object. `run` is the only new collection
command. It calls the existing `TroubleshootingService.run()` entry point after
explicit activation and supplies a cooperative SIGINT cancellation signal.
`show`, `latest`, `compare`, and `export` only read retained schema-v1 sessions.
The reduced `application_failed` profile accepts one validated
`--application-id`.

## Authenticated read-only API

The loopback API adds:

- `GET /api/troubleshooting/latest`;
- `GET /api/troubleshooting/sessions/{session_id}`.

Both require the existing Bearer authentication dependency and reuse the
bounded inspection serializer. API construction and GET requests never create
a service, worker, plan, session, or write. There is no HTTP route for
troubleshooting collection, comparison creation, plan creation, confirmation,
or execution. Invalid IDs fail with 400, unknown IDs with 404, future schemas
with 409, and unavailable current-schema storage with 503.

## Support Bundle v13

`SupportBundleWriter` now emits
`23.0.0-compass-support-v13`. The writer preserves all prior fields and the
v2-v12 reader range. A normal support bundle selects no troubleshooting
session. `troubleshoot export SESSION_ID` selects exactly one known retained
session and includes at most:

- one session;
- 50 findings;
- 25 **Possibly related** change references;
- 25 linked Action Center plan/run status records; and
- one compatible adjacent comparison.

The support case contains no raw stdout/stderr, command or executable field,
credential, token, personal path, hostname, email, IP address, or MAC address.
Recursive stripping and redaction are shared by CLI, API, and support export.
Export can never start troubleshooting collection. Future session or support
schemas fail closed.

## Protected contracts

- All 81 route IDs and six destinations are unchanged.
- `TroubleshootingService.run()` remains the only domain collection entry
  point.
- API token issuance remains the only non-read HTTP method.
- Action Center remains the only host-mutation authority.
- Support Bundle v2-v12 readers and versioned writer classes remain available.
- Product metadata remains v22.0.0 "Alignment".
- The occupied historical `v23.0.0` tag and every remote surface remain
  unchanged.

## Verification

Focused Phase 4 tests cover:

- all six CLI commands and the stable JSON envelope;
- cooperative CLI cancellation wiring;
- exact selected-session export;
- API authentication, GET-only routes, and construction without state reads;
- current-schema inspection and future-schema fail-closed behavior;
- v2-v12 support reader compatibility;
- Support Bundle v13 selection and closed limits; and
- recursive seeded redaction across CLI/API/support payloads.

`just verify` passed on 2026-07-29: lint, mypy, architecture validation,
6,986 tests passed, 61 tests skipped, and coverage was 86.05% against the
required 86%. Phase 5 remains the separate authority for fresh physical
Fedora 44 Traditional and Atomic, Wayland, Orca/AT-SPI, package, performance,
security, installation, and artifact qualification.
