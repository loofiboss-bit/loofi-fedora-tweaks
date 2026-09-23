# Architecture — v30.0.1 "Steady"

Status: local release-candidate contract.

## Product and compatibility boundary

v30.0.1 stabilizes the existing v29.0.1 Utility product. It adds no public
feature or interface. Home, Install, Tune, Fix, Update, Activity & Recovery,
the CLI, JSON envelopes, stable action IDs, saved Action Center formats, and
route redirects retain their current contracts. The historical `v30.0.0` tag
is immutable and is not the source of this candidate identity.

## Mutation authority and durable outcomes

`ActionCenterOrchestrator` remains the sole persistent host-mutation authority.
The PyQt-free `OperationController` owns prepare, confirmation, execution,
verification, and recovery semantics. The Qt adapter owns only one worker
thread and forwards progress and a terminal result.

An operation result is delivered after its worker thread has ended. A late
shutdown request cannot suppress a result after the operation has crossed the
execution boundary. If the result cannot be committed, the UI reflects the
saved run state and asks the user to review Activity & Recovery; it does not
claim success or failure that contradicts durable state. Close and quit remain
pending until worker completion. Only one operation may run per window.

Timeout, malformed executor data, failed verification, awaiting-reboot state,
and resumed verification remain explicit saved outcomes. No automatic retry,
rollback, reboot, or shell execution is introduced.

## Bundles and updates

Install bundles continue through independent items and render every item
result. Ordered Tune bundles stop at the first failed item and mark later items
skipped. Update continues to track System, Flatpak, and Firmware separately;
cancellation marks only its source stale. Action Center run IDs remain the
source of truth for follow-up and verification.

## Page realization and performance

Install, Tune, Fix, and Update are registered as `LazyWidget` placeholders and
constructed on the first route visit. `MainWindow._real_widget_for_entry` is
the existing realization path. Once created, each page instance is reused.
Canonical route resolution, legacy redirects, page signals, and task ownership
remain unchanged.

Startup comparison uses the existing clean-profile offscreen benchmark with
ten measured processes and two warmups on each source revision. Retain lazy
realization only when median startup time or RSS improves by at least 10% and
the other metric regresses by no more than 15%. Thirty route cycles and thirty
worker cycles must leave no QThreads and show no growing window-owned object
count.

## Qualification

Run focused regression tests, the isolated full test/coverage/lint/type and
architecture gate, release and product contracts, packaging checks, and RPM
smoke tests. Physical Fedora desktops, Polkit, Atomic deployment, reboot,
keyboard, and Orca qualification are recorded as `unverified` unless actually
performed. This local candidate does not authorize installation, tagging, or
publication.
