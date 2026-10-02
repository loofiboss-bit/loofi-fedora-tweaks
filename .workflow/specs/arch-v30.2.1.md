# Architecture — v30.2.1 "Comfort" Local Candidate

## Authority and retained boundary

The approved baseline is v30.2.0 at commit `15967f2`. Delivery covers local
implementation, regression coverage, automated qualification, and local RPM
and source artifacts. The public release remains v30.2.0. The subsequent user
request authorizes committing, pushing, and opening a pull request. Merging,
tagging, publication, installation, and persistent host changes are not authorized.

Retain Home, Apps, Tweaks, Health, and Updates, the eight public CLI domains,
all fourteen tweak definitions, the existing action IDs/routes, and the outer
schema-v4 plan/run format. Action Center remains the sole mutation authority.
No dependency, new product feature, generic worker refactor, or tweak redesign
is introduced.

## Stabilization contracts

- Support export applies the shared redactor to every text/JSON archive member,
  reports collection failures, and atomically publishes a private `0600` ZIP.
  Failure preserves an existing destination. Action logs use `0700` directories,
  `0600` files, and a lock covering append and trim.
- Activity owns a closing gate and disconnects result/error callbacks, requests
  cancellation, and waits at most 100 ms. Parentless workers remain retained
  until Qt's actual thread-finished signal, independent of result delivery.
  Invalid dates, non-finite timestamps, and reversed intervals block loading
  before work starts while retaining the displayed snapshot.
- Plan writes/migration use strict schema and record validation, preserving
  corrupt inputs and existing backups and returning recovery guidance.
- Diagnostic collection can return both valid findings and source errors.
  Nonzero exit, timeout, denied access, or malformed source output cannot
  produce healthy status. Partial results preserve useful evidence and source
  failures; disk thresholds parse the actual percent token.
- Firmware policy facts carry version 1 device identity, GUID lists, target
  current/target release versions, and available checksums. Verification binds these facts
  to the same fwupd history device/release, update state, and execution-start timestamp. Insufficient
  legacy firmware plans require fresh review while history remains readable.
- Apps selection lives separately from filtered rows, remains catalog-ordered,
  includes hidden items in summary/review, and is pruned when eligibility changes.

## Qualification and deferred work

Mocked/offscreen tests establish software behavior only. Build local RPM and
source artifacts and exercise read-only `--cli --json info` and
`--cli --json doctor` through an installed RPM in a disposable Fedora container. Fedora 43/44
runtime compatibility and actual package qualification are recorded separately.
Physical KDE/GNOME, Traditional/Atomic, Polkit, keyboard, scaling, and audible
Orca remain `unverified` until independently performed and recorded.

Retired-module cleanup, AppImage work, and a wider distribution matrix are
separate future work. Broad command classification remains a reviewed internal
risk; no public exploit was established by this review.
