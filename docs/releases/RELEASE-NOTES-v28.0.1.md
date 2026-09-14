# v28.0.1 "Ease" — Release Candidate

**Candidate date:** 2026-09-14
**Codename:** Ease
**Publication:** Prepared for the canonical publication workflow; v27.0.1
"Core" remains the current public release until tag and public readback complete.

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

## Local verification status

- Deterministic full suite: 4,790 passed and 73 skipped after the review-fix
  race-lock is synchronized; the suite uses temporary XDG roots.
- Repository-wide local coverage: 87%; the plan's 90% release target remains
  open and is not represented as achieved.
- Lint, typecheck, architecture, product-contract, packaging, and release-doc
  checks are separate gates and must be read back before publication.
- Fedora 43/44 KDE/GNOME, rpm-ostree, Polkit, reboot, Orca, keyboard, theme,
  scale, small-screen, benchmark, and five-user-session gates are unverified.

## Upgrade and publication notes

The v28.0.0 historical workflow-reset record is preserved. This release request
authorizes the commit, push, tag, GitHub release, and COPR publication workflow.
Physical desktop, authorization-agent, reboot, Atomic, accessibility, and
benchmark gates remain separately tracked and explicitly unverified until the
corresponding evidence is collected.
