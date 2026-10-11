# Loofi Fedora Tweaks — Troubleshooting

> Published baseline: v33.0.1 "Concord" (2026-10-12). See [release qualification](V33_QUALIFICATION.md) for the explicit VM E2E exception and physical desktop evidence limits.

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
holds a bounded lease and never retries automatically. For a prepared
traditional Fedora update, an ordinary restart will not start the DNF5 offline
transaction. Select the pending update in **Activity**, choose **Review
recovery**, and inspect the separate Action Center command `dnf5 offline reboot`.
Choose its explicit activation only when you are ready for the computer to
restart immediately. If authorization is cancelled or denied, the original
update remains pending. After restart, select the original update in Activity
and choose **Check result** to verify the actual DNF5 transaction history.

The same flow is available in the CLI. Read the pending run ID from activity
list, prepare and review the activation plan, then explicitly apply that plan:

    loofi-fedora-tweaks --cli activity list --json
    loofi-fedora-tweaks --cli changes apply activate-fedora-offline-update --param source_run_id=RUN_ID --dry-run
    loofi-fedora-tweaks --cli changes apply PLAN_ID --yes --accept-no-rollback

After restart, verify the original prepared update run, not the activation run:

    loofi-fedora-tweaks --cli changes verify RUN_ID

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
