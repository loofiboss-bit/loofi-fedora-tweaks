# Troubleshooting — v27.0.1 "Core"

Start with the read-only diagnostics:

```bash
loofi-fedora-tweaks --cli doctor
loofi-fedora-tweaks --cli --json info
loofi-fedora-tweaks --cli support-bundle
```

Review the support bundle before sharing it. Remove private paths or other
information that is not needed for the issue.

## The application does not start

Check Python, the installed binary, and the desktop runtime:

```bash
python3 --version
command -v loofi-fedora-tweaks
loofi-fedora-tweaks --version
```

For a source checkout:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
PYTHONPATH=loofi-fedora-tweaks python3 loofi-fedora-tweaks/main.py --version
```

Do not run the GUI as root. If Qt reports a missing platform plugin, repair the
desktop's normal Qt/Wayland packages or use the session's documented fallback.

## A source is unavailable

Open **Updates & Apps** and inspect the source details. System packages,
Flatpak, and firmware are independent. Missing binaries, remotes, unsupported
deployment backends, and failed probes stay unavailable/failed; they are not
reported as up to date.

## Authorization does not appear

Reviewed persistent changes use the desktop's standard Polkit agent through
`pkexec`:

```bash
command -v pkexec
pkexec --version
```

If authorization is cancelled, the plan remains unexecuted. Start it again
from **Changes** after the desktop agent is available. Loofi does not install
custom policy files or store credentials.

## A change is stuck or needs a restart

Inspect the plan/run in **Changes**. Do not start a second package transaction.
After using the normal desktop restart controls, run the explicit verification
step for the recorded run. Loofi never reboots, retries, or rolls back
automatically.

## Atomic or bootc host

Run `loofi --json info` and confirm the deployment backend. A staged deployment
may require a restart; unknown or unsupported operations remain unavailable.
See [Atomic Fedora Support](Atomic-Fedora-Support) for the capability-aware
workflow.
