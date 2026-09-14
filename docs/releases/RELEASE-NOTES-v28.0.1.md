# v28.0.1 "Ease" — Public Release

**Release date:** 2026-09-14
**Codename:** Ease
**Publication:** Public, non-draft, non-prerelease GitHub release with a
verified COPR package. See the [public release evidence](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/reports/V28_RELEASE_PUBLICATION.md)
for exact lineage and independent readback.

## Summary

Ease makes the existing Fedora Maintenance Core clearer and more conservative
at the boundaries that matter in daily use. Platform support and deployment
backend decisions now share one typed policy, update inspection publishes
source-owned partial results, and Activity & Recovery can continue through
bounded pages without turning storage errors into empty success.

## Implemented

- Centralized Fedora 43/44 stable, Fedora 45 preview, and unknown support
  classification across profile, onboarding, doctor, navigation, updates, and
  Action Center eligibility.
- Kept DNF, rpm-ostree, bootc, and unknown deployment backends separate;
  bootc and unknown system updates fail closed with explicit guidance.
- Added bounded concurrent update inspection, cancellation, per-source retry,
  immediate source completion, atomic schema-v2 persistence, and retention of
  the last known candidate list after a failed probe.
- Distinguished missing, empty, partial, corrupt, and future-schema history;
  added a bounded opaque continuation cursor to Change Journal and CLI activity
  listing.
- Made fresh update sources open a direct `Review <source> updates` path while
  keeping Changes as the only review, execution, verification, and recovery
  authority.
- Addressed review feedback by making retained observations round-trip safely,
  invalidating them across backend/support-policy changes, gating direct review
  on the supported platform policy, resetting Activity pagination on filter
  changes, exposing CLI continuation markers, and keeping read-only Home
  construction free of history-directory creation.
- Reused the active Action Center catalog for search and added order-independent
  task language for freeing disk space, updates, and a slow system.
- Added plain-language checked-result and next-step facts to Changes and
  redirected tests to temporary XDG roots.

## Compatibility

Existing GUI routes, CLI commands, JSON envelopes, v27 history readers, and
future-schema preservation remain in place. The optional `activity list
--cursor` argument extends the existing read-only command without changing its
default output contract. No new runtime dependency, background service, host
setting, reboot, or direct UI mutator was introduced.

## Verification status

- Deterministic full suite: 4,790 passed and 73 skipped after the review-fix
  race-lock is synchronized; the suite uses temporary XDG roots.
- Repository-wide local coverage: 87%; the plan's 90% release target remains
  open and is not represented as achieved.
- Lint, typecheck, architecture, product-contract, packaging, and release-doc
  checks passed as separate gates before publication.
- Fedora 43/44 KDE/GNOME, rpm-ostree, Polkit, reboot, Orca, keyboard, theme,
  scale, small-screen, benchmark, and five-user-session gates are unverified.

## Upgrade and publication notes

The v28.0.0 historical workflow-reset record is preserved. The commit, push,
tag, GitHub release, COPR publication, and public readback are complete.
Physical desktop, authorization-agent, reboot, Atomic, accessibility, and
benchmark gates remain separately tracked and explicitly unverified until the
corresponding evidence is collected.
