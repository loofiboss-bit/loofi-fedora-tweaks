# v17 Phase 1 -- Assurance Core and Read-only API

Date: 2026-07-20
Status: complete

- Action plans and runs use schema v2; v1 read triggers an atomic, backed-up,
  readback-verified migration and future schemas remain read-only.
- `VerificationDecision` owns `succeeded`, `awaiting_reboot`, and `failed`.
  Runs persist execution boot ID, reboot status, attempts, and last verification.
- Definition-specific validation rejects unknown, mistyped, URL, option-like,
  retention, and backend inputs before command construction.
- Verification receives the original digest-protected plan and the durable run.
- `/api/execute`, profile writes, and persisted observability snapshot writes
  were removed. `GET /api/observability/current` collects without persistence.
- Full FastAPI route-table coverage proves token issuance is the only non-GET
  API operation.

Existing expiry, fresh preflight, digest, mutation lease, confirmation,
no-rollback acknowledgement, and no automatic retry/reboot/rollback contracts
remain enforced.
