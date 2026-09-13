# Workflow Quickstart — v27.0.1 "Core"

This repository uses `.workflow/specs/` as the active release planning area.

For v27.0.1 Core work:

- Read `.workflow/specs/.race-lock.json` before release-scoped edits.
- Keep the current release target and public tag unique; historical tags are
  never moved.
- Keep route IDs in `core/navigation` as the canonical persisted navigation surface.
- Keep the default sidebar focused to Home, Software & Updates, System & Hardware, Network & Security, and Desktop & Settings.
- Use `docs/README.md`, `CHANGELOG.md`, and `ROADMAP.md` as active documentation indexes.
- Run `just verify` or the explicit validation commands from `docs/RELEASE_CHECKLIST.md` before release.
- Keep Fedora KDE 44 as the supported target and Fedora 45 as preview-only advisory context.
- Keep all host mutations behind Action Center review and preserve explicit
  unavailable/manual states on unsupported platforms.
