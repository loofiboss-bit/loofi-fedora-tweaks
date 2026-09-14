# Release Notes -- v28.0.2 "Ease"

**Release Date:** 2026-09-14
**Codename:** Ease
**Theme:** Fail-closed battery-service cleanup

## Summary

v28.0.2 is a focused patch release following the v28.0.1 Ease release. It
resolves the remaining battery-service review findings from PR #40 while
preserving the existing Fedora Maintenance Core boundaries and Action Center
authority.

The patch advertises only the implemented standard sysfs battery backend and
makes privileged service cleanup explicit, validated, bounded, and fail-closed.

The public release is available as
[v28.0.2 on GitHub](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v28.0.2).
Exact tag lineage, assets, checksums, attestations, COPR publication, and
documentation readback are recorded in the
[public release evidence](../reports/V28.0.2_RELEASE_PUBLICATION.md).

## Highlights

- Removed the unused HP BIOS configuration path from battery support detection.
- Centralized battery cleanup commands in the audited `PrivilegedCommand`
  builders.
- Treats a failed or timed-out cleanup step as an unsuccessful cleanup instead
  of reporting a misleading success.
- Added regression coverage for command validation, cleanup ordering, failures,
  exceptions, and unsupported hardware.

## Changes

### Changed

- Standard sysfs support is the only advertised implemented battery-service
  backend; unsupported firmware-specific paths remain unavailable.
- Cleanup now disables the service, removes the generated unit, reloads the
  user service manager, and resets the failed state through bounded privileged
  command execution.

### Added

- Validated builders for `systemctl disable --now`, daemon reload, failed-state
  reset, and `rm -f -- <path>`.
- Explicit return-code and exception handling for every cleanup operation.

### Fixed

- Prevented misleading battery-service support claims for an unimplemented HP
  BIOS backend.
- Prevented cleanup from reporting success when a privileged command fails,
  times out, or raises an operating-system error.
- Prevented ambiguous removal paths by validating the target and placing `--`
  before the path passed to `rm`.

## Verification

- **Focused tests:** 59 passed.
- **Full local `just verify`:** 4,804 passed, 73 skipped, 830 subtests passed,
  14 warnings, and 0 failures.
- **Coverage:** 86.64% repository-wide against the maintained 85% blocking
  gate.
- **Lint, type checking, architecture, stabilization, security, and release
  documentation checks:** passed locally.

Physical Fedora, authorization-agent, reboot, fresh Atomic, keyboard, Orca,
and clean-install gates remain separate manual evidence and are not inferred
from rootless or offscreen verification.

## Upgrade Notes

No migration or user-configuration changes are required. The release does not
install, enable, or mutate a host service by itself; reviewed persistent
changes continue to flow through the existing Action Center authority.
