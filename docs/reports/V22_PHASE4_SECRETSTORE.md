# V22 Phase 4 — Provider-neutral SecretStore evidence

## Contract

- SecretStore continues to use the Python keyring abstraction without checking
  or migrating any named provider.
- Persistent writes require exact provider readback before they are reported as
  persistent.
- Missing or locked providers fall back to process-memory storage for reads and
  writes; no plaintext fallback is created.
- Delete removes the session copy first, reports locked/provider failures, and
  treats an already-missing persistent secret as deleted.
- Empty account identifiers are rejected before a provider call.

## Verification

Focused tests cover persistent CRUD, unavailable and locked backends, session
fallback, delete failure and missing-secret behavior, fail-closed readback, and
backend initialization failure.

- `PYTHONPATH=loofi-fedora-tweaks python -m pytest tests/test_secret_store.py tests/test_auth.py tests/test_haven_contracts.py tests/test_cloud_sync.py -q`
  — 52 passed, one existing PyGI deprecation warning.
- Scoped `python -m flake8` for the implementation and affected tests — passed.
- Scoped `python -m mypy` for `core/secrets.py` and the provider contract tests
  — passed.
- `git diff --check` for the implementation, tests, and this report — passed.
