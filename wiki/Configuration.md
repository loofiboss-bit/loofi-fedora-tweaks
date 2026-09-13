# Configuration — v27.0.1 "Core"

Application settings are opened from the header gear. The GUI stores only
Loofi-owned preferences and review history under the user's XDG directories;
host changes still require an explicit Action Center plan.

## State and recovery

State files use versioned schemas, atomic writes, bounded leases, and
last-known-good backups. Future schemas remain read-only. Support exports are
redacted and do not include passwords, tokens, private keys, raw credentials,
or executable extension code.

The supported user-facing recovery path is:

1. Open **Settings** or **Changes** and inspect the state explanation.
2. Create or review a backup when the UI offers one.
3. Generate a recovery plan.
4. Confirm the plan explicitly and inspect the resulting verification.

There is no direct state-restore command that bypasses the plan boundary.

## Preferences

Theme, notification, navigation, safety, and display preferences are local
application state. Resetting a preference group does not execute a host
mutation. Favorites and saved routes are migrated conservatively; unknown or
retired routes remain unavailable instead of being redirected to a different
operation.

## Environment and diagnostics

Use the documented CLI for inspection:

```bash
loofi-fedora-tweaks --cli --json info
loofi-fedora-tweaks --cli doctor
loofi-fedora-tweaks --cli support-bundle
```

`LOOFI_IPC_MODE=disabled` is a test/qualification setting, not a normal user
configuration. The Core product has no local Web API, D-Bus daemon, remote
configuration fetch, or unattended scheduler.

## Privacy

Support bundles are created locally and should be reviewed before sharing.
Never paste secrets into issue reports or into action parameters. Loofi does
not ask for or persist administrator passwords; Polkit handles authorization
through the desktop agent.
