# Personal qualification

Local candidate: v32.6.0 "Personal", 2026-10-09, built on the included Companion
32.5 work. This document separates automated checks, read-only host observations,
and physical interaction. No installation or publication was performed.

## Automated checks

Final integrated checks passed on the Fedora 44 development host:

| Check | Result |
| --- | --- |
| `LOOFI_IPC_MODE=disabled QT_QPA_PLATFORM=offscreen just verify` | Passed: lint, mypy, architecture, catalog/version; 5,038 tests and 2,041 subtests; 33 skipped; coverage 85.45% |
| `just check-packaging` | Passed: dependency synchronization and built wheel/sdist manifest |
| `just build-rpm` | Passed: `1:32.6.0-1.fc44.noarch` |
| RPM payload readback | All 23 changed production Python modules and the compressed manpage match the current source bytes |
| `git diff --check` | Passed |
| Independent focused reviews | Completed; parser compatibility, partial RPM evidence, source layout and native-reader ownership findings corrected |

The navigation lifecycle regression initially measured object counts while the
new asynchronous inventory was legitimately adding rows. A delayed fixture
reproduced the transition. The test now uses fixed inventory/source observations
and waits within a bounded deadline before asserting stable page identity,
QObject ownership, no retained QThreads and exactly one initial query per reader.
The final lifecycle/integration group also passed all 19 tests.

The local RPM is
`rpmbuild/RPMS/noarch/loofi-fedora-tweaks-32.6.0-1.fc44.noarch.rpm`, with SHA256
`093aef9ab5214207db3b4ff62d1c81988f1edf0c778174b4d49ce96529c69e8a`.
This is local build evidence; no public provenance or release is claimed.

Focused regressions cover desktop-entry visibility and localized names, escaped
strings, duplicate launchers and installed package architectures, shared time
budgets, unowned files and partial ownership failures. Profile tests cover copy
creation without applying settings, original and opaque-row preservation,
unsupported targets, write errors and drift before reviewed application. Source
tests cover one shared GUI observation, CLI text/JSON, duplicate JSON fields and
IDs, malformed responses, missing tools, timeout and legacy upgrade preparation.
KDE tests cover command allowlists, stored verification, runtime enum
normalization, custom-value restoration, drift and failed activation. Integration
tests cover lazy Updates-to-Apps navigation and pending native-launch shutdown.

The isolated fixture rendering matrix captured 56 views: seven new scenarios,
light/dark presentation, two window sizes (900×650 and 1280×800), and 100%/200%
scale. Automated focus traversal reported no missing focus targets; clipping
probes reported no clipped scenarios. Installed apps, profile editing, sources,
window controls and native-link cards were visually inspected. Long repository
values remain elided with full-value tooltips. These fixtures mock readers and
external launches; they do not establish physical keyboard or external-window
behavior. Local captures and reports are under `/tmp/fedora-personal-ui/`.

## Read-only Fedora 44 KDE observations

- The actual installed-app inventory returned 91 RPM applications and 10
  Flatpaks in about 1.5 seconds, with no read errors or unknown sources.
- Local DNF configuration returned 55 repositories. The actual
  `--cli --json updates sources` command also succeeded with 55 repositories.
  Network availability was not checked.
- Stored placement was `Centered`, and both stored snap distances were `10`.
  KWin support information reported matching `placement`, `borderSnapZone` and
  `windowSnapZone` values. This confirms reading and normalization for the
  current state, without testing a change or restore.
- Availability discovery found `kcm_componentchooser`, `kcm_autostart` and
  `kcm_icons`. External settings windows were not launched.

No host settings were written, KWin activation signals sent, services restarted,
or application start commands executed by these checks.

## Remaining physical qualification

Native computer-control APIs were unavailable in this task. The candidate still
requires physical KDE checks for the three window controls: reviewed apply,
visible session effect, restore including custom prior values, and failed
activation feedback. Default Applications, Autostart and Icons handoffs require
actual external-window checks. Physical keyboard use, 200% desktop scaling and
assistive technology remain unverified; automated fixture focus and rendering
are the evidence described above.

GNOME shared workflows and Atomic restrictions have automated coverage only;
neither platform received physical qualification in this task. No support scope
was expanded for Atomic systems.

## Preserved boundaries

- RPM is an installation mechanism, not proof of Fedora repository provenance.
  Only explicitly curated catalog applications receive recommendation labels.
- Discovery reads desktop metadata and RPM ownership without evaluating launch
  commands. Bounded partial evidence is reported rather than hidden.
- Saving a profile modifies only the content-addressed local library. Applying
  it requires fresh review, drift checks, sequential execution and verification.
  The portable format remains `loofi.tweak-profile/v1`.
- Sources describe cached local DNF configuration. They do not change repository
  activation or test connectivity; failed reads remain unknown.
- KDE stored-state verification and session activation have separate outcomes.
  New controls use the existing Action Center and restoration mechanisms.
- Commit, pull request, release, package installation and publication require a
  separate instruction.
