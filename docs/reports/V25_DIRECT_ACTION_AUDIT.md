# v25.0.4 “Proof” Direct-Action Audit

**Status:** release evidence, generated from the v25.0.4 Proof checkout on
2026-08-12. This report covers software contracts; it is not a physical-host
qualification claim.

## Scope and authority

The audit reads the canonical `ActionCatalog` and classifies each registered
`ActionDefinition` through `core.actions.eligibility.classify_definition`.
There is no second executable-action allow-list. The Action Center metadata is
the source of truth; missing, malformed, unsupported, or unsafe metadata can
only lower authority to review or blocked.

The direct path remains a policy adapter over Action Center:

```text
request → catalog definition → plan → fresh preflight → confirmation policy
        → Action Center apply → independent verification → typed outcome
```

It does not accept arbitrary command vectors, execute from preview/dry-run,
bypass leases or audit records, retry automatically, resume interrupted work,
or turn a manual/high-risk action into direct execution.

## Catalog result

The current catalog contains 74 first-party definitions. The read-only audit
returned:

| Eligibility kind | Count | Policy |
| --- | ---: | --- |
| `direct` | 5 | Low-risk and complete metadata; fresh preflight still required |
| `confirmation` | 5 | Medium-risk; one compact confirmation when enabled |
| `review_required` | 64 | Full Action Center review or manual guidance |
| `blocked` | 0 | No unknown IDs were present in the registered catalog |

The 64 review-required definitions consist of 61 `manual_only` definitions and
3 high-risk host definitions. The complete direct and confirmation sets are:

### Direct

- `create-recovery-point`
- `dnf-clean-all`
- `fstrim-all`
- `install-application`
- `update-flatpaks`

### One compact confirmation

- `autoremove-packages`
- `remove-application`
- `restart-failed-service`
- `update-fedora-system`
- `vacuum-journal`

### Review-required high-risk host actions

- `dnf5-history-undo`
- `rpm-ostree-rollback`
- `update-firmware`

Every other catalog item is explicitly `manual_only` in the current metadata
and remains non-executable through the Proof direct path. Unknown IDs return
`unknown_action` and `blocked`; incomplete metadata returns
`incomplete_action_metadata` and `review_required`.

## Required metadata

Before a definition can be classified, the audit requires valid:

- stable action and capability IDs;
- presentation text and a closed parameter schema;
- risk and confirmation policy;
- recovery guidance and an explicit rollback capability;
- operation class and Traditional/Atomic variant declaration;
- reboot policy and bounded affected-resource list;
- command renderer, preflight checker, and verifier callables.

The current 74-definition catalog passed this structural audit. Regression
tests also replace required metadata with an incomplete value and verify that
the result cannot become direct.

## Verification boundary

Rootless tests cover unknown, manual-only, high-risk, incomplete, medium-risk,
dry-run, review-first, preflight-blocked, typed-parameter, Action Center
authority, and no-fallback-executor behavior. Physical Fedora KDE Wayland,
Polkit interaction, reboot completion, accessibility, manual recovery, public
release, and package-installation claims remain outside this local audit and
are recorded as `unverified` or `blocked` in the qualification report.
