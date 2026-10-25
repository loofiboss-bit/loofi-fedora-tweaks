# Fedora KDE VM end-to-end tests

> GitHub self-hosted runner execution is retired. See
> [manual qualification](MANUAL_VM_QUALIFICATION.md) for the trusted source handoff,
> resource-profile distinction, and evidence requirements. The commands below
> describe the preserved legacy controller; they are not automatic CI gates.

`just test-full` builds the current RPM, installs it into a dedicated Fedora
KDE guest, runs native desktop tests through AT-SPI, collects JUnit and log
reports, then discards the guest overlay. The first run installs a reusable
Fedora 44 KDE base image; later runs reuse that image and start with a clean
QCOW2 overlay.

## Selenium AT-SPI

Loofi is a native PyQt application. Tests use pytest and Selenium's Python
client against KDE's Selenium AT-SPI server, bound to guest localhost. The
server exposes Qt accessibility controls and the separate Polkit dialog through
a desktop session. The guest uses Plasma X11 so native input does not require
KDE's additional Wayland input/screenshot build tools.

The two upstream Python driver files are pinned to commit
`50e41aa9913b16e5d0a6fec921c963485aa125b4`, checked against recorded SHA-256
hashes, and cached in the private VM data directory. They are fetched once and
reused, including when the guest overlay is discarded. Update the revision and
both hashes together in `e2e/vm.py` when deliberately upgrading the driver.
Upstream source and license: [KDE Selenium AT-SPI](https://github.com/KDE/selenium-webdriver-at-spi)
(AGPL-3.0-or-later). The upstream source is not copied into this repository.

The Fedora KDE Live ISO is not used by this unattended installer. Anaconda
does not support Kickstart installation when booted from the Live OS, so the
first run fetches the Fedora 44 Everything installation tree over the guest's
outbound-only network. No local ISO or manual VM setup is needed.

## Stable native control contracts

Application tabs use the real Qt tab-list focus and horizontal arrow keys.
The helper verifies the selected tab after input; virtual child-tab geometry
or a successful input call alone does not prove that the view changed.
Guide resumption opens the accessible menu and waits for the exact named next
step before selecting it. The native guide menu retains focus actions and
exposes its popup as an accessible child; blind positional Home/Enter input is
not used to infer navigation.
The installed inventory check explicitly starts Refresh and observes its
enabled → disabled → enabled cycle with cancellation and bounded deadlines.

Setting results are scoped to the exact accessible setting-status row and
check both Requested and Verified values, restoration status, and relevant
session-activation guidance. Tests also read KDE or DNF configuration directly
after a change and restoration. A successful status on another row cannot
satisfy the check. Actions are not automatically retried on assertion failure.

Completed runs print their status and report directory. Failed runs also print
a bounded excerpt of the collected, credential-redacted pytest log, including
the correct reboot phase when applicable. JUnit, logs, and accessibility trees
remain the detailed evidence; guest shutdown and overlay cleanup still run on
success, failure, or interruption. Host regressions for these helpers live in
`tests/test_e2e_native_input.py`, `tests/test_e2e_refresh_observation.py`, and
`tests/test_e2e_vm_contract.py`.

## Host requirements

Run as the normal desktop user, never with `sudo` or `pkexec`. The runner does
not install packages, start host services, alter libvirt networks, or change
host configuration. It uses only `qemu:///session`; it does not connect to or
modify system libvirt VMs.

The host must have:

- Fedora with `/dev/kvm` readable and writable by the user.
- `virsh`, `virt-install`, `qemu-img`, `qemu-system-x86_64`, `rpmbuild`,
  `openssl`, `just`, and Python 3 for `just test-full`.
- pytest and the repository's Python test dependencies for the separate host
  test suite; GUI automation dependencies are installed only in the guest.
- At least 6 GiB `MemAvailable` and 40 GiB free on the data filesystem before
  starting. The guest is fixed at 5 GiB RAM and 2 vCPUs; the remaining memory
  sets a 1 GiB host margin above the guest allocation.
- Outbound access to Fedora's Fedora 44 Everything repository on the first
  provisioning run.

The runner checks these conditions before building the RPM or creating a VM.
Missing host tools are reported exactly; approve and install them separately
before retrying. Guest-only packages such as `python3-selenium`, `python3-flask`, and
`python3-pyatspi` are installed inside the VM, not on the host.

## Isolation and lifecycle

- VM name: `loofi-fedora-tweaks-e2e` on `qemu:///session`.
- Persistent data: `${XDG_DATA_HOME:-~/.local/share}/loofi-fedora-tweaks/e2e/`.
- Reports: `test-results/e2e/` in the current checkout.
- The guest has QEMU user-mode networking for outbound traffic, no host-shared
  filesystem, no forwarded inbound ports, and Spice bound to `127.0.0.1`.
  The network link is disabled in the reusable test domain: ordinary test runs
  are offline, including desktop background update checks. Only initial Fedora
  provisioning and the first checksum-verified driver fetch use networking.
- The host transfers the RPM and pytest files through QEMU Guest Agent. The
  commands execute through the authenticated guest serial login because SELinux
  confines guest-agent processes. The guest applies package and settings changes; a fresh overlay is created from
  the immutable base before and after each run.
- The reusable base contains the RPM's runtime dependencies. Each run installs
  the locally built RPM directly with `rpm`, without refreshing repository
  metadata or downloading packages. Add new application dependencies to the
  Kickstart package list when the application requires them; RPM then fails
  clearly if a dependency is missing from the guest.
- The guest test account has a randomly generated password kept in the private
  VM data directory with mode `0600`; it authenticates the serial login and exercises the guest's
  Polkit dialog and is not printed in reports.
- Credential integrity metadata uses PBKDF2-HMAC-SHA256 with a unique 128-bit
  salt, 600,000 iterations, and constant-time comparison. It is separate from
  the guest account's authentication hash and never replaces guest PAM/Polkit.
- The VM's domain UUID, memory, CPU, disk, user network, graphics binding,
  filesystem devices, and passthrough devices are checked before boot. An
  existing VM with a different identity is never stopped or replaced.

Run these commands from the repository root:

```bash
just test-full-preflight
just test-full
```

`test-results/e2e/summary.json` records the result, preflight facts, and the
exact RPM filename and SHA-256 hash.
`junit.xml`, `pytest.log`, `install.log`, and `application.log` are collected
when available. Runtime logs may help diagnose guest or desktop failures.

If first-time provisioning fails while the runner is active, it stops and
removes only the partial VM and generated files created by that invocation so
the next `just test-full` can retry. If the host or runner is interrupted before
that cleanup completes, the next run resumes an owned installed disk when
possible. Use `just test-full-reset` only to deliberately discard that data. Reset checks
the saved UUID, VM disk path, network, memory, CPU, graphics binding, and
passthrough devices before it stops a partial domain. It refuses an unmarked
or mismatched VM and leaves its files untouched.

## Additional qualification runs

The legacy `just test-full` keeps its X11 guest. Hosted CI and manually
recorded native qualification have separate trust and evidence boundaries.
Run qualification variants sequentially; do not start multiple 5 GiB guests on
the same host. These options add coverage and do not imply a successful run:

```bash
just test-full-reboot
just test-full-fresh
just test-full-wayland
```

`test-full-reboot` runs the normal suite with a before-reboot checkpoint,
collects its reports, requests an agent-mediated reboot of the UUID/shape-validated
disposable domain, and independently reads `/proc/sys/kernel/random/boot_id`.
A different valid boot ID is mandatory before running the after-reboot suite.
The tests compare saved guide data and Dolphin settings, reopen the guide,
and restore the setting through the app with independent readback. The overlay
remains the same across reboot and is discarded only after qualification ends.

`test-full-fresh` provisions from an empty disk in a newly named domain and a
unique `fresh-x11-<id>` data/report directory. It never replaces or resets the
usual golden image. The runner prints both exact directories; keep them with
the qualification report. The resulting separate base is retained as an owned
artifact, while test changes are discarded in its overlay. Initial installation
requires outbound Fedora access and can take up to 90 minutes.

The ordinary Wayland variant uses a separate `wayland/` data directory and
`loofi-fedora-tweaks-e2e-wayland` domain. SDDM starts Plasma Wayland; session
socket detection and environment capture distinguish Wayland from its Xwayland
compatibility display. Qt uses `wayland`, and native input is sent through the
actual guest KWin process. Missing helper binaries fail with actionable output.
KDE documents these helpers and compositor requirements in its
[Appium automation guide](https://develop.kde.org/docs/apps/tests/appium/).

During initial Wayland provisioning only, Kickstart installs Fedora development
packages in the guest and builds the input and screenshot helpers from the same
pinned KDE revision as the Python driver:
`50e41aa9913b16e5d0a6fec921c963485aa125b4`. The source archive must match SHA-256
`8e71bfbd93a5760f08b87ae437087847d2ec376bd88858bee5a4e228f1fcaba0` before
extraction/build. Only the two helper binaries and their desktop permission
metadata are installed; build source is removed. No build dependencies are
installed on the host. This is additional guest infrastructure, not evidence
that physical Wayland input or a human screen reader has been qualified.

Each normal suite also stages an inert local `loofi-e2e-fixture-1.0-1.noarch`
RPM containing only `/usr/share/loofi-e2e-fixture/probe.txt`. The fixture test
uses the guest's graphical Polkit flow and DNF5 in cache-only mode, independently
queries RPM identity/file verification, checks the probe payload, removes the
fixture without automatically removing dependencies, and compares the complete
installed RPM inventory with its original state. This qualifies the native
package transaction; it does not prove an app store's package-removal UI.

Before-reboot reports retain their ordinary names. After-reboot reports use
`-after-reboot` before their extension (for example
`junit-after-reboot.xml` and `pytest-after-reboot.log`). `summary.json` records
final cleanup status, exact RPM hash, desktop and both boot IDs.
`package-fixture.log` and `reboot-checkpoint.json` are collected when available.
The runner removes known reports at the beginning of each run, so a previous
successful checkpoint cannot qualify a later failure.

The suite stops at its first failure and records the failing accessibility tree
when available, avoiding secondary failures from inherited dialogs. Native input
helpers run with Qt debug logging disabled: upstream debug output may otherwise
include synthesized credential keystrokes. Warnings and errors remain available.
Refresh qualification requires an observed enabled → disabled → enabled cycle
and a known installed-app result; an already-enabled button alone is insufficient.
App restart resolves exactly one live suite-owned process and refuses ambiguity.

Reset a separate fresh artifact only with the exact printed data root, recorded
domain name and desktop. Ownership checks still validate the UUID and device
shape before stopping or deleting anything:

```bash
python3 -m e2e.vm reset --data-root /absolute/printed/fresh-x11-ID \
  --vm-name loofi-fedora-tweaks-e2e-fresh-x11-ID
python3 -m e2e.vm reset --desktop wayland
```

For a fresh Wayland artifact, supply `--desktop wayland`, its exact data root
and its exact `--vm-name`; explicit names avoid appending another `wayland/`
directory. Arbitrary or unmarked domains remain refused. The regular
`just test-full-reset` continues to address only the default X11 artifact.

## What is exercised

The pytest suite navigates between Tweaks and Activity, changes and restores a
per-user Dolphin setting, verifies the inline success state, rejects a
system-change confirmation, cancels a Polkit request without changing DNF,
then authorizes a DNF change and restarts the app. It verifies that the DNF
value and restoration offer survived the restart, restores the prior value,
and reads the actual DNF configuration after the change and restoration.
When authorization is cached, the helper accepts it only after that external
readback reaches the requested value. The guest is reset even when pytest
fails. Tests and future workflows belong under `e2e/tests/`;
the normal host suite remains isolated under `tests/`.

Add a pytest test or module under `e2e/tests/` and use the `loofi_app` fixture
and accessible-name helpers. The runner stages all Python files there
automatically. Failed tests save an accessibility tree; a validated artifact
manifest discovers new test reports without adding names to the host runner.
Prefer small reversible settings and verify their actual saved value before
restoration. Keep privileged changes in the guest's existing Polkit flow.

Host tool output uses a fixed locale, including on Swedish desktops. SIGINT
and SIGTERM request a prompt hard stop of only the owned disposable guest and
discard its overlay. After an abrupt process kill or laptop restart, the next
run acquires the exclusive lock and validates ownership and isolation before
stopping any abandoned test guest. Recovery runs before the memory check so
the abandoned guest cannot consume the RAM needed by the next test run.

Provisioning marks Plasma's first-run setup complete before enabling the login
manager. Fedora's KDE environment includes that setup flow, which otherwise
logs into a separate setup account before the desktop test account. This keeps
the first boot unattended and lets the configured Plasma X11 autologin start through SDDM. SELinux remains
enforcing; the guest-agent policy is unchanged. At each run, only the guest
staging directory is labeled `virt_qemu_ga_log_t`, the existing agent file
transfer type. This permits payload/report transfer without granting the
agent desktop or system administration access.

## Hosted CI and manual native qualification

Automated workflows use GitHub-hosted runners. The former self-hosted jobs,
workflow inputs, and release dependencies are retired. An unavailable laptop
cannot leave a required VM job queued. Native results are recorded separately
using [manual qualification](MANUAL_VM_QUALIFICATION.md); hosted CI success
never claims a native desktop, reboot, or physical test passed.

The historical `e2e.ci_runner` bootstrap is not part of the supported workflow.
Do not register the desktop as a GitHub runner or re-enable its retired user
service. The native test controller itself remains available under the legacy
resource and trusted-source conditions documented above.

## Implementation qualification (2026-10-11)

Validated on the Fedora 44 KDE laptop with the reusable guest:

- Two consecutive unattended RPM/build/install/GUI/report/reset runs passed
  all six E2E tests after the Polkit synchronization change. Each run used the
  offline disposable guest and reset it afterward. The DNF flow verified
  persisted setting/history after app restart and direct system-state readback
  after restoration.
- An actual SIGTERM stopped the owned guest and recreated its empty overlay
  in 0.47 seconds. Recovery of an intentionally abandoned owned guest was
  exercised. A diagnostic run exposed a lost serial prompt; the permanent
  prompt retry was subsequently covered by regression and unattended VM tests.
- The immutable base's inode, size, modification time and read-only mode
  remained unchanged. `qemu-img check` reported no errors, and the final run
  overlay occupied 200,704 bytes after reset.
- The repository runner was registered and confirmed online through GitHub;
  its systemd user service was enabled and active. No host Fedora packages
  were installed by this implementation.
- The final host pytest suite passed 5,191 tests with 33 skips and 13 warnings.
  Application lint, type checking, architecture checks, E2E infrastructure
  lint, and host GUI-suite refusal checks passed.

The golden guest was initially installed with Anaconda and finalized while
debugging the desktop and automation setup. The final Kickstart incorporates
those corrections, but a completely fresh installation from an empty disk
was not rerun after the final corrections. The qualified path is reuse of
the existing golden guest. This qualification covers local execution;
GitHub workflow/release execution must be assessed separately.
These VM tests cover Plasma X11, and do not qualify physical hardware,
the host's Plasma Wayland session, or GNOME.

## Signed DNF5 offline reboot qualification

`just test-full --reboot-check` now uses a signed inert RPM upgrade through the
installed application's `OperationController`, rather than using a generic VM
reboot as evidence of an applied update. Use a newly provisioned base (`--fresh`)
for the guest-only `rpm-build`, `rpm-sign`, and `createrepo_c` dependencies.
Missing dependencies fail qualification; they are never installed on the host.

After desktop tests pass, the root guest runner creates versions 1.0 and 2.0 of
one inert package, an ephemeral signing identity, signed RPMs, and signed local
repository metadata. Both versions remain in the signed repository. Action Center installs the exact
1.0 NEVRA, rejects a now-stale installation review, removes 1.0, and reinstalls
it with fresh reviews. Every operation receives independent RPM/payload,
unrelated-package and preserved-data readback. External
repository definitions are moved aside inside the disposable overlay. Action
Center reviews and stages the 2.0 update; the harness confirms that staging has
not changed the installed inventory. The separate activation action requests
DNF5's offline reboot. No direct DNF upgrade or generic hypervisor reboot is
used as a substitute.

After the kernel boot ID changes, Action Center verifies the original durable
run. The root harness independently checks the exact installed package, RPM
file integrity, DNF5 history and package health, unchanged unrelated packages,
and preserved data. The after-reboot pytest phase checks the recorded evidence.
`application-action-evidence.json`, `offline-update-evidence.json` and
`offline-activation.log` are collected with
both phases' reports.

Independent history validation records existing transaction IDs before staging
and requires a new successful transaction starting at or after the staged run.
Its separate `history info` must contain the exact target version and an inbound
package action; the full matched details are retained. Empty, old, failed or
mismatched history cannot pass because the product verifier succeeded.

This root harness qualifies the installed application backend and real reboot
chain. It does not exercise the desktop activation dialog; GUI authorization
and accessibility need their own final-RPM candidate run. The new chain has
only been checked with rootless host contracts during implementation. No VM
pass is claimed until the full candidate has actually completed it.

## Source, codec and first-install fixtures

The before-reboot runner also executes `setup_transaction_fixture.py` inside
the marked disposable QEMU guest. Source activation uses the unchanged pinned
RPM Fusion public key and the installed OperationController/helper logic. Only
the exact allowlisted key download is supplied from staged public bytes. The
fixture checks review drift before confirmation and again under the helper
lock. It does not qualify public HTTPS availability or desktop Polkit.
It also holds the actual source lock in a separate process and verifies that
confirmed apply fails without package or configuration changes.

Codec replacement runs the installed native libdnf5/helper logic against a
separate installroot and signed inert FFmpeg/GStreamer recipe packages. It
checks separate removal consent, complete inventory readback and unrelated
package/data preservation. It does not replace the guest's desktop codec stack
or qualify media playback. Its native Base configuration is redirected before
setup; production guards, signatures, resolution and execution stay active.
`setup-transactions.log` and `setup-transactions-evidence.json` record the
result separately from desktop pytest and offline reboot evidence.
Confirmed source drift and a conflicting pair of signed fixed-recipe packages
exercise native rejection. The latter requires the actual resolver conflict,
rather than accepting any unavailable preview as conflict evidence.

`test_02_flatpak_installs.py` follows the v34 update matrix with a distinct
signed application that was never preinstalled. It uses the installed
OperationController and native Flatpak/Polkit for user, system and named
installations, checks exact commits/origins and preserved unrelated refs/data,
and rejects a changed-source review before mutation. Evidence is collected as
`flatpak-install-evidence.json`. These new fixtures remain unqualified until
the exact candidate completes them in the guest.
