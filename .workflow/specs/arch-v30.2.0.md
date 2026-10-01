# Architecture — v30.2.0 "Comfort"

## Product and authority

The five primary destinations and existing routes/action IDs remain valid.
The PyQt-free catalog/action layers retain Action Center as sole mutation
authority. The baseline is v30.1.0 master `737a550`. The user authorized full
GitHub, COPR, and wiki publication on 2026-10-01. Workstation installation
remains outside scope.

## Closed settings

The catalog grows from eight to fourteen definitions. KDE adds file opening,
double-click interval, smooth scrolling, and scrollbar clicks. GNOME adds clock
format and weekday display. Visibility is scoped by immutable desktop and
deployment capabilities: seven KDE rows and eight GNOME rows including power.
Unknown and bootc backends remain blocked. Policy accepts only reviewed keys,
argument shapes, and types, never a generic configuration writer.

## Durable restoration

Normal tweak runs capture exact before/after values and tweak identity as
versioned metadata under the existing `verification_result.data`. The atomic
store and outer schema-v4 contract remain unchanged. Each `restore-*` action
accepts only `source_run_id`; domain logic derives all writable values from
verified stored evidence. Fresh preflight requires unchanged current state,
latest normal run, no later change attempts, valid bounds/choices, and an
unconsumed source. Legacy/missing/pruned evidence cannot enable restore.
Numeric values preserve precision; removed schemes/profiles block restoration.

Restore is a new confirmed operation with independent verification. Only
verified successful restoration consumes eligibility. There is no redo,
automatic rollback, or mass operation. State acknowledgement failures must
not report saved success. GUI rows show availability, current values, eligible
restoration and honest results while the shared controller rejects overlap.
Saved configuration verification does not establish active KDE application
effects; UI explains reopening where needed.

## Qualification

Mocked/offscreen checks establish software behavior only. The local evidence
report records exact automated and package checks. Physical KDE/GNOME,
Traditional/Atomic, keyboard, scaling, and Orca claims require separate evidence.

### Custom scalar restoration bounds

Restoration preserves the captured scalar without display rounding. GNOME text
scale must be between 0.5 and 3; KDE animation duration must be finite and
nonnegative; KDE double-click interval must be an integer between 100 and
2000 ms. These custom values come only from verified saved evidence, not
arbitrary caller input. Invalid or unreadable values block modification.
