# Care qualification

Verification evidence captured for the v32.4.0 "Care" release candidate on 2026-10-07 and 2026-10-08.
The v32.4.0 RPM was installed on the host from a target-only DNF5 transaction.
At capture time, the change was on open PR #56 and had not been merged or published.

## Automated checks

- `just verify` passed: 4,888 tests, 33 skipped, 1,961 subtests, and 85.27%
  coverage (the repository threshold is 85%).
- `just check-packaging` passed, including the source and package manifest check.
- `just build-rpm` produced
  `rpmbuild/RPMS/noarch/loofi-fedora-tweaks-32.4.0-1.fc44.noarch.rpm`.
  RPM `%check` imported the app and validated AppStream metadata.
- `git diff --check` passed.
- The existing control-center rendering script captured 225 views at each of
  100%, 150%, 200%, and large-text settings, including Apps and Health. Its
  clipping, control-text, table-theme, and horizontal-scroll checks reported
  zero issues in every pass. These are offscreen layout checks.

## Real Flatpak fixtures

The fixtures used local build-export repositories and synthetic app/runtime
refs. Shared-scope runs took place in the disposable Fedora 44 Podman container
`loofi-care-qualification`, with a test-only Polkit rule for its `care-fixture`
user. Each run used `umask 077` to exercise shared-installation permission
handling. No applications were downloaded or launched.

| Installation | Reviewed runtime removed | Other refs preserved | App data preserved | Stale review blocked | Cross-install runtime protected |
| --- | --- | ---: | --- | --- | --- |
| user | yes | 3 | yes | yes | not applicable |
| system | yes | 3 | yes | yes | yes |
| named `care-fixture` | yes | 3 | yes | yes | yes |

Each run also exercised the Action Center operation and confirmed local EOL
metadata for both the app and runtime. The system and named runs installed a
synthetic user-scope app without its runtime, removed the fixture app from the
selected shared installation, then confirmed that its referenced runtime was
not offered for cleanup.

## Additional coverage and limits

Unit tests cover duplicate refs across installations, EOL and missing-runtime
details, unknown size, combined source/scope filters, absent optional
libflatpak support, changed commits and pins, unexpected transaction
operations, transaction failure, cancellation, partial cleanup, and observed
results in Activity. CLI and GUI update diagnostics use the same source status
service and preserve source and run identity.

Physical KDE/GNOME behavior, screen-reader use, hardware input, and interactive
Polkit prompts remain unverified. The render matrix is not a substitute for
those checks. At capture time, the RPM installation and PR push had completed
separately; merge and publication had not.
