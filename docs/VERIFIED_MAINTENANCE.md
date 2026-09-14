# Verified Maintenance

Loofi Fedora Tweaks v28.0.3 "Ease" uses the **Action Center** as the one trust
boundary for persistent system changes from both GUI and CLI. Updates & Apps
can start and finish supported daily updates in place; Changes remains the
shared history and advanced review surface.

## The lifecycle

Open **Updates & Apps** for daily system, Flatpak, and firmware updates, or
open **Changes** to inspect **Needs attention** or **Recent**. Catalog browsing,
search, and details are inert. A plan is created only after a fresh preflight;
sensitive actions add one concrete confirmation.

Every review shows five facts:

1. **Change** — the exact intended operation and affected resources;
2. **Risk** — impact and scope;
3. **Authorization** — why the desktop may request administrator approval;
4. **Verify** — the independent state check that follows execution; and
5. **Recovery** — rollback or the precise manual limitation.

The lifecycle is:

```text
preflight → review → explicit authorization → bounded run → independent verify
```

Plans expire and are re-preflighted immediately before execution. One
cross-process mutation lease prevents concurrent host changes. A process exit
code alone is never presented as verified success. Interrupted, failed, and
restart-required runs remain visible and require an explicit follow-up.

## Capability-aware actions

An action is available only when its platform capability, risk, authorization,
verification, and recovery contract are known. Traditional Fedora, Atomic
Fedora, and bootc deployments have different package and restart semantics.
Unknown detection fails closed.

Supported source-specific maintenance can include:

- system package updates;
- Flatpak updates when the command and remote are available;
- firmware status and update handoff;
- bounded package-cache cleanup;
- selected service or firewall changes with an exact verifier; and
- recovery-point creation or supported rollback guidance.

Application discovery is handed to the desktop's native software center when a
capability-aware AppStream handoff exists. Loofi is not distributed as a
Flatpak and does not silently add remotes.

## CLI

```bash
loofi-fedora-tweaks --cli changes list
loofi-fedora-tweaks --cli changes show PLAN_ID
loofi-fedora-tweaks --cli changes apply PLAN_ID --yes
loofi-fedora-tweaks --cli changes verify RUN_ID
```

Use `--json` before the command for machine-readable output. The CLI
accepts only the closed catalog and typed parameters; it has no arbitrary shell
or remote execution mode.

## What never happens automatically

Loofi does not perform unattended schedules, fix-all operations, automatic
restart, retry, rollback, or resume. A manual-only or unavailable action is
shown with its reason and safe alternative. Cancelling authorization leaves the
plan unexecuted.

## Evidence and support

Action verification and System Check resolution are separate facts. A linked
run waiting for restart remains pending until the new deployment is explicitly
verified and a later compatible check confirms the relevant state.

Support bundles contain bounded, redacted diagnostic evidence. They do not
contain secrets, raw process output, arbitrary command vectors, or executable
repair instructions. Review any archive before sharing it.
