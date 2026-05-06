# Release Notes -- v7.0.0 "Aegis"

**Release Date:** 2026-05-06  
**Codename:** Aegis  
**Theme:** Safe guided actions and Fedora 44 reliability

## Summary

v7.0.0 "Aegis" focuses on safe guided actions, release reliability, support diagnostics, and Fedora KDE 44 polish. It keeps readiness checks read-only by default, adds a reviewable Action Inbox for selected findings, and requires explicit confirmation before any supported mutating action can run.

Fedora KDE 44 is the supported target. Fedora 45 remains only an existing preview/advisory profile and is not a v7 release theme.

## Highlights

- Guided Action Bridge for readiness action planning, preview, confirmation, run, and verification.
- Safer readiness action planning with manual-only recommendations blocked from execution.
- Support Bundle v5 with action candidates, recent action history, package health, service/journal signals, and stronger redaction.
- Stricter release gates for metadata, docs, workflow specs, coverage thresholds, and release claims.
- Fedora 44 readiness wording and support summaries polished for beginner and advanced modes.
- Documentation and design consistency updates, including semantic Plugin SDK icon guidance.

## Added

- `core/diagnostics/readiness_actions.py` for `ReadinessActionPlan` and `ReadinessActionCandidate`.
- CLI commands: `readiness actions`, `action-info`, `action-preview`, `action-run --confirm`, and `action-verify`.
- In-dialog Action Inbox in the existing Release Readiness UI.
- `core/export/support_bundle_v5.py` with recursive redaction and v4-compatible readiness fields.

## Changed

- Runtime, Python project, RPM, workflow, README, roadmap, changelog, and release notes now identify v7.0.0 "Aegis".
- CI and auto-release coverage gates now enforce 80 consistently.
- Readiness JSON excludes advanced-only fields unless `--advanced` is passed.
- Fedora KDE 44 remains the default supported readiness target.

## Fixed

- Release-doc validation now catches stale README badges/text, ROADMAP active release drift, CHANGELOG drift, missing release notes/specs, race-lock drift, coverage threshold mismatches, and docs-only CI bypasses.
- Existing diagnostics typecheck blockers were fixed before expanding mypy scope.
- Support bundle redaction now masks home paths, emails, and token/password/secret/key-like values recursively.

## Safety Notes

- Readiness checks remain read-only by default.
- There is no automatic repair and no fix-all button.
- Manual-only recommendations cannot be executed by Loofi Fedora Tweaks.
- Executable readiness actions fail without explicit confirmation.
- Privileged actions route through existing `pkexec` and ActionExecutor conventions.

## Upgrade Notes

- Use `loofi-fedora-tweaks --cli readiness --target 44` for the supported Fedora KDE 44 profile.
- Use `loofi-fedora-tweaks --cli readiness actions --target 44` to review action candidates.
- Use `loofi-fedora-tweaks --cli readiness action-preview <action-id> --target 44` before running any action.
- `loofi-fedora-tweaks --cli fedora44-readiness` remains available as a compatibility alias.

## Validation Stats

- **Release docs:** `just validate-release` passed on 2026-05-06.
- **Adapter drift:** `just check-drift` passed on 2026-05-06.
- **Stabilization rules:** `PYTHONPATH=loofi-fedora-tweaks python3 scripts/check_stabilization_rules.py` passed on 2026-05-06.
- **Tests:** `PYTHONPATH=loofi-fedora-tweaks python -m pytest tests/ -v` passed with 7344 passed, 48 skipped, 9 warnings, and 182 subtests passed.
- **Tests and coverage:** `PYTHONPATH=loofi-fedora-tweaks python -m pytest tests/ -v --cov=loofi-fedora-tweaks --cov-fail-under=80` passed with 7344 passed, 48 skipped, 182 subtests passed, and total coverage 80.00%.
