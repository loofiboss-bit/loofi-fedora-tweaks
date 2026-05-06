# Architecture — v7.0.0 "Aegis"

## Goals

- Keep Fedora KDE 44 as the supported target and preserve Fedora 45 only as an advisory preview profile.
- Turn read-only readiness findings into safe, reviewable action plans without automatic repair.
- Reuse existing Atlas action/executor and `pkexec` conventions for any mutating action.
- Improve support diagnostics, release metadata correctness, and beginner/advanced presentation without adding a permanent tab.

## Decisions

- `core/diagnostics/release_readiness.py` remains the read-only readiness engine.
- `core/diagnostics/readiness_actions.py` owns action candidate generation, preview, confirmation-gated run, and verification.
- Most recommendations are manual-only in v7; only the explicitly mapped low-risk package-cache cleanup candidate is executable.
- `cli/main.py` exposes nested `readiness` action commands while keeping `readiness --target 44` and `fedora44-readiness` compatibility.
- `ui/release_readiness_dialog.py` gains an in-dialog Action Inbox; it never calls subprocess directly and never offers a fix-all action.
- `core/export/support_bundle_v5.py` is the current support bundle generator; v3/v4 import paths remain compatibility wrappers.
- `scripts/check_release_docs.py` is the release metadata and claim parity gate for README, ROADMAP, CHANGELOG, release notes, workflow specs, race-lock, CI coverage, and docs-only CI behavior.

## Validation

- `just validate-release`
- `just check-drift`
- `PYTHONPATH=loofi-fedora-tweaks python3 scripts/check_stabilization_rules.py`
- `PYTHONPATH=loofi-fedora-tweaks python -m pytest tests/ -v`
- `PYTHONPATH=loofi-fedora-tweaks python -m pytest tests/ -v --cov=loofi-fedora-tweaks --cov-fail-under=80`
