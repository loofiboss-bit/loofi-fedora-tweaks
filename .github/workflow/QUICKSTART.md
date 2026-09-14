# Workflow Quickstart — v28.0.3 "Ease"

This repository uses `.workflow/specs/` as the active release planning area.

For v28.0.3 Ease work:

- Read `.workflow/specs/.race-lock.json` before release-scoped edits.
- Keep the current release target and public tag unique; historical tags are
  never moved.
- Keep route IDs in `core/navigation` as the canonical persisted navigation surface.
- Keep the default sidebar focused to Home, Updates & Apps, System Health, Protection & Recovery, and Changes.
- Use `docs/README.md`, `CHANGELOG.md`, and `ROADMAP.md` as active documentation indexes.
- Run `just verify` or the explicit validation commands from `docs/RELEASE_CHECKLIST.md` before release.
- Keep Fedora KDE 44 as the supported target and Fedora 45 as preview-only advisory context.
- Keep all host mutations behind the Action Center authority. Normal Updates &
  Apps work may begin on its owning page; preserve explicit unavailable/manual
  states on unsupported platforms.
- Automated checks are the publication gates. Record physical/manual evidence
  as verified, pending, or unverified without blocking release closure.
