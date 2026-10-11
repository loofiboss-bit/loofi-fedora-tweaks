# Fedora KDE VM end-to-end tests

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

## What is exercised

The pytest suite navigates between Tweaks and Activity, changes and restores a
per-user Dolphin setting, verifies the inline success state, rejects a
system-change confirmation, cancels a Polkit request without changing DNF,
then authorizes a DNF change and restores its prior value. The guest is reset
even when pytest fails. Tests and future workflows belong under `e2e/tests/`;
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

## CI and release runner

Pull requests use the existing hosted CI checks and do not execute repository
code on a trusted self-hosted machine. Push and release workflows add a
`vm_e2e` job requiring a self-hosted runner labeled
`loofi-vm-e2e`. Configure that runner on the Fedora KDE host with the host
requirements above and the repository checkout available to GitHub Actions.
If no matching runner is online, the job remains queued; the auto-release RPM
build and publication depend on its success. The workflows upload the E2E
reports as an artifact even when the VM test fails.

The CI runner must be dedicated to trusted repository branches and releases.
Do not add the label to a shared machine that runs untrusted pull-request code.

## Approving the local CI runner

The VM tests do not install a GitHub Actions runner on the host. This separate
setup requires explicit host approval. Inspect its exact plan without changing
anything:

```bash
python3 -m e2e.ci_runner
```

After approval, run:

```bash
python3 -m e2e.ci_runner --approve-host-change
```

The approved actions are downloading the official Linux x64 runner with size
and SHA-256 verification, registering `loofi-fedora-tweaks-vm` for this
repository using `gh`, and creating/enabling/starting
`~/.config/systemd/user/loofi-fedora-tweaks-ci-runner.service`. The binary and
CI checkout live under `~/.local/share/loofi-fedora-tweaks/ci-runner/`; GitHub's
standard runner updates stay there. No Fedora system packages are installed.
If a native runner dependency is missing, setup fails and reports it rather
than executing GitHub's host dependency installer. Existing unrelated runner
data or services are refused. Setup confirms the runner's online status.

The user service is available while the user's systemd manager runs. Host
login lingering is not enabled; offline/suspended laptops leave VM jobs queued.
Inspect or stop the service with:

```bash
systemctl --user status loofi-fedora-tweaks-ci-runner.service
journalctl --user -u loofi-fedora-tweaks-ci-runner.service
systemctl --user disable --now loofi-fedora-tweaks-ci-runner.service
```

## Implementation qualification (2026-10-11)

Validated on the Fedora 44 KDE laptop with the reusable guest:

- Two unattended complete RPM/build/install/GUI/report/reset runs passed all
  three GUI workflows. The final run used Swedish host locale, blocked host
  external HTTP access, and the guest's disabled network link.
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
