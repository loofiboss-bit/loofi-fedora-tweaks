# Loofi Fedora Tweaks v25.0.4 “Proof” — Release Notes

**Release Date:** 2026-08-12
**Codename:** Proof

## Summary

Proof adds a bounded direct-action path over the existing Action Center. An
eligible request follows one observable lifecycle: plan, fresh preflight,
optional confirmation, execution, independent verification, and typed outcome
evidence. The release uses `v25.0.4` because historical `v25.0.0`–`v25.0.3`
tags are preserved on separate pre-Proof lineages.

## Highlights

- Fail-closed eligibility is derived from canonical Action Center metadata;
  unknown, incomplete, manual-only, high-risk, unsupported, unverifiable, and
  future-schema requests remain review-only or blocked.
- Safety & Execution settings provide direct and review-first modes, medium-risk
  confirmation, preview, automatic verification, and safe future-schema
  handling.
- `DirectActionService` is a PyQt-free adapter over Action Center plan, lease,
  preflight, execution, verification, interruption, and recovery authority.
- `loofi run ACTION_ID [--param KEY=VALUE] [--yes] [--dry-run] [--json]`
  accepts only registered actions and typed parameters.
- Home and Activity & Recovery expose pending work, reboot hand-off, verified
  outcomes, source quality, evidence detail, recovery readiness, filters, and
  privacy-redacted JSON/Markdown export.

## Safety and compatibility

The six top-level destinations, stable routes, lazy loading, Traditional and
Atomic behavior, Action Center CLI compatibility, API/daemon read-only
boundary, and existing persisted state remain intact. No arbitrary shell
input, unattended execution, automatic retry, automatic rollback, automatic
reboot, external executable plugin path, or direct Undo path was introduced.

Physical Fedora KDE Wayland, fresh Atomic/Kinoite, Polkit, reboot, keyboard,
screen-reader, and manual recovery qualification remain separate manual gates.
They are not inferred from rootless/offscreen evidence and are reported as
`unverified` in the qualification record.

## Verification

- Full rootless `just verify`: **7107 passed**, 61 skipped, 20 warnings, 1239
  subtests, 86.25% coverage.
- Proof-focused regression set: **153 passed**, 21 skipped, 1 warning.
- Release documentation, project stats, adapter drift, packaging manifest,
  product contract, architecture contract, and System Check contract passed.
- Public tag, GitHub Actions, release assets, checksums, attestations, COPR,
  and wiki readback are recorded in
  [`V25_RELEASE_PUBLICATION.md`](../reports/V25_RELEASE_PUBLICATION.md).

## Upgrade notes

Existing state remains readable. New Safety & Execution state uses a versioned
XDG schema with atomic writes; malformed or future schemas fail closed to
review-first behavior. Direct execution never bypasses Action Center authority.
