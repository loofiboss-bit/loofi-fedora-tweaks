# Architecture — v10.0.0

## Goals

- Promote release readiness from a modal diagnostic into a guided upgrade-planning workflow.
- Keep Fedora KDE 44 as the stable supported target and Fedora 45 as a preview-only profile.
- Reuse existing Home, Maintenance, readiness dialog, action inbox, support bundle, and route-manifest contracts instead of adding a new permanent plugin tab.
- Preserve existing route IDs, plugin IDs, CLI compatibility, favorites, and saved settings.

## Decisions

- Extend `ReleaseTarget` with local release-profile metadata for status, phase, upgrade source, important changes, known risks, and documentation links.
- Add Fedora 45 preview checks as read-only diagnostics in `ReleaseReadiness`; all mutating follow-up remains in readiness actions with explicit confirmation.
- Add `maintenance:upgrade-assistant` as a subroute of the existing Maintenance plugin.
- Keep SupportBundleV5 import compatibility while emitting the v10 support-v6 schema and new release-planning fields.
- Keep coverage enforcement at the existing 84% gate unless focused v10 tests can raise it safely.

## Validation Contract

- `ReleaseReadiness.run()` defaults to Fedora 44 and accepts `mode="upgrade-plan"` without breaking existing callers.
- `readiness plan`, `readiness explain`, and `readiness export` support JSON and text output.
- Navigation validation covers the new Maintenance subroute without renaming existing routes.
- Smart Updates scheduled commands reject invalid package names and do not use shell execution.
