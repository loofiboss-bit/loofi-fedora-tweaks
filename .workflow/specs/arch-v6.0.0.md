# Architecture — v6.0.0

## Goals

- Keep v6 architecture-focused and user-facing without broad feature expansion.
- Generalize Fedora KDE 44 readiness into target-driven release readiness.
- Preserve read-only diagnostics by default.
- Surface beginner guidance separately from advanced diagnostic detail.
- Keep optional API/daemon RPM dependencies out of the base GUI/CLI package.

## Decisions

- `core/diagnostics/release_readiness.py` owns target metadata, scoring, typed checks, and recommendation metadata.
- `core/diagnostics/fedora44_readiness.py` stays as a compatibility facade for one major release.
- UI code calls the service/core readiness API asynchronously and never executes subprocesses directly.
- CLI command `readiness` is the canonical interface; `fedora44-readiness` remains a compatibility alias.
- Support Bundle v4 stores generic `release_readiness` data while keeping the v3 `fedora_kde_44_readiness` field as an alias for older consumers.
- Fedora KDE 44 is the supported target. Fedora 45 is preview-only and returns advisory status.
- Mutating repair work is intentionally out of scope unless modeled through existing Atlas action metadata and `pkexec` conventions.

## Validation

- `just validate-release`
- `just check-drift`
- `PYTHONPATH=loofi-fedora-tweaks python3 scripts/check_stabilization_rules.py`
- `just test`
- `just test-coverage`
