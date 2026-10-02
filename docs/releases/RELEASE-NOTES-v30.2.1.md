# Release Notes — v30.2.1 "Comfort" Local Candidate

**Candidate date:** 2026-10-02. Local implementation and qualification only.
The current public release remains v30.2.0; this candidate is not published
or installed on the workstation.

## Changes

- Redact every text/JSON member of support archives; report unavailable sources
  explicitly and publish completed archives atomically with private permissions.
- Protect and lock action logs across append and trimming.
- Keep Activity workers alive until actual thread termination, including
  cancelled results, and stop new collection during page cleanup.
- Reject invalid, non-finite, and reversed date filters before collection
  without discarding the previous result.
- Block writes/migration over corrupted plan storage while preserving original
  state and backup files and explaining recovery.
- Correct disk-use parsing and retain useful findings with explicit partial
  source failures; failed probes cannot establish healthy state.
- Verify firmware with structured device/GUID, target-release, checksum, and
  update-state and current-run timestamp evidence from the corresponding history record.
- Keep app selections across search/category changes, with complete summary
  and review, and remove selections when eligibility changes.
- Synchronize the manual, candidate metadata, and active documentation.

## Qualification and compatibility

The maintained coverage gate is 85 percent. Full verification, local RPM/source
builds, artifact identity, and isolated read-only packaged `info`/`doctor` smoke
are recorded in the [candidate qualification report](../reports/V30.2.1_LOCAL_QUALIFICATION.md) after execution. Older
release test counts are not evidence for this candidate.

Fedora 43 and 44 are runtime compatibility targets, separate from actual RPM
qualification. Physical KDE/GNOME, Traditional/Atomic, Polkit, keyboard,
scaling, and audible Orca remain `unverified`. Mocked/offscreen checks do not
establish real-device firmware or physical session behavior.

## Upgrade and authority

The five destinations, eight CLI domains, fourteen tweaks, routes/action IDs,
and outer schema-v4 plan/run storage remain unchanged. Firmware facts gain
versioned device/release evidence; old firmware plans with insufficient facts
require new review. Existing history remains readable. Corrupt state must be
preserved and repaired through explicit recovery before saving new plans.

Baseline: v30.2.0 commit `15967f2`. Authorized delivery includes local fixes,
regression tests, verification, and local packages. A subsequent user request
authorizes commit, push, and pull request creation. Merging, tags, publication,
installation, and host changes require separate instruction.
Retired-module cleanup, AppImage, and a broader package matrix are deferred.
