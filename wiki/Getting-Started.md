# Loofi Fedora Tweaks — Getting Started

> Version 24.0.0 "Flow"

<!-- Canonical source mirrored byte-for-byte to wiki/Getting-Started.md. -->

Use this guide for a safe first run in under 10 minutes.

---

## 1) Install and launch

```bash
pkexec dnf copr enable loofitheboss/loofi-fedora-tweaks
pkexec dnf install loofi-fedora-tweaks
loofi-fedora-tweaks
```

Optional CLI alias:

```bash
alias loofi='loofi-fedora-tweaks --cli'
```

The first launch opens Home with integrated guidance. It can be dismissed or
resumed, remembers your step, and only opens existing pages. It does not run a
check, install packages, create a plan, start services, or modify the host.

Loofi detects the Fedora variant automatically. Traditional Fedora uses DNF;
Atomic Fedora uses rpm-ostree-aware or manual-only paths where an operation is
not safe to automate.

---

## 2) Learn the UI in 30 seconds

The primary shell has exactly six destinations:

1. **Home**
2. **Software & Updates**
3. **System**
4. **Network & Security**
5. **Desktop**
6. **Settings**

Pages load when you open them. Specialist development, automation,
virtualization, local-profile, and sharing tools remain grouped and searchable
under **Specialist Tools**. Built-in pages load on demand; external Python
plugins and the public Marketplace are retired.

Useful shortcuts:

- `Ctrl+K` opens global search for routes, settings, and safe action entries.
- `Ctrl+Shift+K` opens the same policy-backed search model filtered to actions.
- `F1` opens shortcut help.

Search results obey the same Fedora-variant, component, and safety policy
as normal navigation. Search may open or preselect an Action Center item, but it
never plans or runs an action.

![Loofi Home](https://raw.githubusercontent.com/loofiboss-bit/loofi-fedora-tweaks/master/docs/images/user-guide/home-dashboard.png)

---

## 3) Five Core Workflows

### Update the system

Open **Software & Updates → Updates**, review the available updates, and create
a plan. Action Center shows the exact plan before a separate apply step.

![Maintenance Updates](https://raw.githubusercontent.com/loofiboss-bit/loofi-fedora-tweaks/master/docs/images/user-guide/maintenance-updates.png)

### Install an application

Open **Software & Updates → Applications**, select an application, and create a
review plan. Installing never starts as a side effect of creating the plan.

### Diagnose a slow system

Open **System → Performance** and run **Analyze Slow System**. The result uses a
bounded, read-only snapshot and links to supporting process or storage details.

![System Monitor](https://raw.githubusercontent.com/loofiboss-bit/loofi-fedora-tweaks/master/docs/images/user-guide/system-monitor.png)

For guided troubleshooting, open **System → Troubleshooting**, select a problem
profile, review its sources, and start the bounded read-only collection
explicitly. A result may show one safe next step; it never repairs the system
automatically.

### Free disk space

Open **Software & Updates → Cleanup** and run the reclaim analysis before
deleting or trimming anything. Review each category separately.

### Protect or recover the system

Open **System → Recovery Points** to create or inspect snapshots. Use
**Network & Security → Backups** for guided backup and restore workflows.

---

## 4) Verified Maintenance

Open **Software & Updates → Action Center** for supported maintenance actions.
Action Center applies the same safety lifecycle to all supported host changes:

1. Review the exact action and preflight evidence.
2. Create an expiring plan.
3. Confirm the reviewed plan explicitly.
4. Accept missing rollback only when the UI requires it.
5. Run one bounded mutation at a time.
6. Verify the outcome separately.

The 74 first-party definitions declare their operation class, Fedora variants,
reboot policy, affected resources, confirmation, verification, and recovery
policy. Unsupported host operations remain `manual_only`. Loofi never treats
command exit code zero as verified success by itself.

Safe CLI examples:

```bash
loofi action-center list --target 44
loofi action-center history --limit 10
loofi readiness --target 44
loofi action-center plan dnf-clean-all
loofi action-center show PLAN_ID
```

Creating a plan does not apply it. Review and apply the exact plan separately
in Action Center.

---

## 5) Weekly Routine

1. Check Home for prioritized attention items.
2. Review and install system updates.
3. Run reclaim analysis instead of direct broad cleanup.
4. Check System performance and storage when something feels slow.
5. Create a recovery point before risky work.
6. Review Action Center history after verified maintenance.

---

## 6) Useful CLI Commands

```bash
loofi info
loofi health
loofi troubleshoot profiles
loofi troubleshoot run system_slow
loofi troubleshoot latest
loofi fedora44-readiness
loofi readiness actions --target 44
loofi doctor
loofi security-audit
loofi support-bundle
```

---

## 7) Next Docs

- [Full user guide](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/USER_GUIDE.md)
- [Fedora KDE 44 readiness](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/FEDORA_KDE_44_READINESS.md)
- [Verified maintenance](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/VERIFIED_MAINTENANCE.md)
- [Advanced operations](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/ADVANCED_ADMIN_GUIDE.md)
- [Troubleshooting](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/master/docs/TROUBLESHOOTING.md)
