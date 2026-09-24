# Loofi Fedora Tweaks — Troubleshooting

> Version 30.1.0 "Personalize" local candidate; publication is pending.

Use this guide when the application or one of its Fedora checks is unavailable.
Loofi reports missing capabilities explicitly and does not guess a desktop,
deployment backend, or restart state.

## Start with diagnostics

Run the read-only doctor command:

```bash
loofi-fedora-tweaks --cli doctor
```

Then collect a redacted support bundle:

```bash
loofi-fedora-tweaks --cli support-bundle
```

Review the bundle before sharing it. Include the version, Fedora release,
architecture, desktop/session, exact page or command, and reproduction steps in
an issue. Do not include passwords, tokens, or unreviewed command output.

## The application does not start

Check the basic runtime and try the version command:

```bash
python3 --version
loofi-fedora-tweaks --version
command -v loofi-fedora-tweaks
```

For a source checkout, use an isolated environment and the repository's
runtime path:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
PYTHONPATH=loofi-fedora-tweaks python3 loofi-fedora-tweaks/main.py --version
```

The application writes startup diagnostics below
`~/.local/share/loofi-fedora-tweaks/`. A missing desktop notification utility
does not prevent the GUI from starting.

## A source is unavailable

Open **Update** and inspect the source details. System packages,
Flatpak, and firmware are independent sources. Missing binaries, missing
remotes, unsupported deployment backends, and failed probes are reported as
unavailable or failed; they are never converted to “up to date”.

Use `loofi check` to create a fresh read-only System Check. A partial result is
useful evidence but is not a clean bill of health.

## Authorization does not appear

Persistent changes request authorization through `pkexec` and the desktop's
standard authorization agent. Confirm that the command exists and that your
desktop session has an active agent:

```bash
command -v pkexec
pkexec --version
```

If authorization is cancelled, the plan remains unexecuted. Start the task
again from its owning page after the agent is available. Loofi does not install
custom Polkit policy files and cannot grant administrator access to a user.

## An action is unavailable

Open its details on the owning page. An action is intentionally unavailable when
capability, risk, authentication, verification, or recovery information is
missing. Unknown desktop/session/backend detection fails closed. On Atomic
hosts, some operations require a staged deployment and a later restart; follow
the explicit handoff and verify only after Fedora reports the deployment as
booted.

## Updates or changes are stuck

Inspect **Activity & Recovery** and use the recorded explanation. Do not run a
second package transaction while one is active. A running or interrupted plan
holds a bounded lease and never retries automatically. If a restart is
required, restart the host using the normal desktop controls, then return to
**Activity & Recovery** and run the explicit verification step.

## Flatpak-specific checks

Flatpak is an optional update source, not an installation format for Loofi.
If the `flatpak` command or the configured remote is missing, the source is
shown as unavailable. Use the desktop software center or Flatpak's own tools to
repair remotes; Loofi does not silently add a remote or install a sandbox.

## Package repair

Reinstall the published RPM from the configured Fedora repository:

```bash
pkexec dnf reinstall loofi-fedora-tweaks
```

For a source checkout, rerun the package installation command from
[Getting Started](BEGINNER_QUICK_GUIDE.md). Package removal preserves user
configuration, check results, action history, and backup metadata.

## Report a bug

Before reporting, record:

- `loofi-fedora-tweaks --version` output;
- the Fedora release and architecture;
- desktop and session, if known;
- the exact destination, action, or CLI command;
- whether the issue occurred during check, review, run, or verification; and
- a reviewed support bundle when diagnostics are relevant.

File issues at the [project issue tracker](https://github.com/loofiboss-bit/loofi-fedora-tweaks/issues).
