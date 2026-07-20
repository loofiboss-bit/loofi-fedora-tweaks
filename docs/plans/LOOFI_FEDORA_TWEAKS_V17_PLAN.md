# Loofi Fedora Tweaks v17.0.0 "Assurance"

## Canonical implementation plan

v17 makes the five canonical workflows preview-first, explicitly confirmed,
audited, and outcome-verified through Action Center. It preserves the v16
navigation, startup, state, plugin, CLI read, daemon, and IPC contracts while
removing unsupported remote mutation from the Web API.

### Required outcomes

- Extend the deny-by-default Action Center catalog with independently planned
  Fedora, Flatpak, firmware, application, cleanup, and recovery-point actions.
- Add plan-aware verification and a durable `awaiting_reboot` lifecycle without
  automatic reboot, retry, rollback, or resume.
- Route the five canonical workflow mutations through Action Center; keep
  diagnosis read-only and unsupported recovery/destructive work manual-only.
- Make every non-token Web API route read-only.
- Preserve v16 meaningful-Home and resource budgets.
- Keep specialist tools in the base RPM; physical `-extras` packaging is not a
  v17 deliverable.

### Phases

1. Baseline and scope lock.
2. Assurance lifecycle v2 and read-only API.
3. Independent Fedora, Flatpak, and firmware update plans.
4. Application install/remove plans.
5. Read-only diagnosis plus verified cleanup plans.
6. Verified Timeshift/Snapper recovery-point creation and surface convergence.
7. Full regression, performance, packaging, release readiness, and version
   synchronization.

### Frozen boundaries

- Stable route IDs, aliases, destination placement, lazy loading, favorites,
  saved navigation state, and Home/search handoffs.
- Existing Action Center IDs and v1 persisted records.
- Traditional and Atomic Fedora command-policy and privilege boundaries.
- CLI read commands, read-only API responses, daemon, D-Bus, and IPC.
- One plan, one regenerated command vector, one explicit confirmation, and one
  independently verified run.

### Explicit non-goals

- No multi-action transaction or Update All execution queue.
- No Advanced-route migration, remote apply, automatic repair, or automatic
  reboot/rollback/retry.
- No raw Btrfs recovery-point execution and no automated restore/delete.
- No physical core/extras package split.

### Release gates

- Full verification and at least 85 percent coverage.
- Traditional and Atomic contract matrices, reboot-resume coverage, API route
  audit, packaging/security checks, and real installed-runtime evidence.
- Meaningful Home no slower than `min(Phase 0 * 1.20, 225 ms)`; RSS no more than
  Phase 0 * 1.15; zero startup probes, active timers, QThreads, or specialist
  plugin instances.
