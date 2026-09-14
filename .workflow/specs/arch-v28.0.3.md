# Architecture — v28.0.3 "Ease"

Status: direct maintenance execution release candidate.

## Goals

- Let normal system and Flatpak updates start and finish from Updates & Apps.
- Keep Action Center as the sole persistent-mutation authority.
- Give sensitive operations one concrete, prepared-scope confirmation.
- Preserve fresh preflight, privilege checks, mutation leases, verification,
  and fail-closed unsupported-platform behavior.
- Treat physical/manual qualification as supplementary evidence recorded in the
  release report rather than a publication prerequisite.

## Decisions

- `DirectActionService` and `ActionCenterOrchestrator` provide the shared
  asynchronous prepare, authorize, execute, and verify lifecycle. No alternate
  command path or new dependency is introduced.
- Action definitions carry technical `risk_level` and independent
  `interaction_policy`. Automatic updates can run directly while high-risk
  operations remain confirmation- or review-gated.
- GUI direct mode is a local presentation policy. An explicitly persisted
  `review_first` preference still requires local confirmation and cannot be
  bypassed by a direct button.
- Plan and run stores use shared schema version 4. Older supported records
  migrate; future records are preserved read-only and report the affected
  Action Center function plus a concrete recovery step.
- Traditional Fedora and rpm-ostree are handled separately. bootc and unknown
  mutation paths remain unavailable with an explicit explanation.

## Verification policy

The blocking publication gates are automated tests, static analysis,
architecture and trust-boundary checks, packaging, security analysis, and
release-document validation. Physical Fedora, Polkit-agent, reboot, Atomic,
keyboard, Orca, and clean-install checks may be run as supplementary evidence;
their status is recorded as verified, pending, or `unverified` and never blocks
publication. Automated offscreen/rootless evidence must not be presented as
physical qualification.
