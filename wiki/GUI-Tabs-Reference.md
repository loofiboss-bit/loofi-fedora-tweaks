# GUI Destinations — v27.0.1 "Core"

The v27 shell has five primary destinations. The labels are stable and the
content is capability-aware; unavailable features are explained rather than
silently replaced by a different desktop assumption.

1. **Home** — system state, one recommended next action, and common tasks.
2. **Updates & Apps** — system, host Flatpak, and firmware inspection, plus a
   native software-center handoff.
3. **System Health** — read-only System Check, symptom troubleshooting,
   storage, hardware status, and support bundle export.
4. **Protection & Recovery** — firewall/exposure, backups, recovery points,
   exact backend-aware rollback guidance, and activity history.
5. **Changes** — Action Center plans, authorization, execution, and independent
   verification.

Settings opens from the header gear and is not a sixth primary destination.
The navigation adapts between expanded, icon-rail, and compact selector
layouts as window width and text scale change.

## Safety

Opening a destination is read-only. Persistent changes must be reviewed and
confirmed in **Changes**. Search navigates to pages and safe action entrypoints
but cannot execute a host change. No automatic reboot, retry, rollback, or
unattended schedule is exposed.

Historical specialist routes remain only as compatibility explanations and are
not current GUI destinations.
